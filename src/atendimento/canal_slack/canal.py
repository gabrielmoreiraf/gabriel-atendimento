"""Espelho do Canal do time no Slack e decisões pelos botões (P5, HP-10, HG-10, HG-20).

O canal do time continua sendo `agente.canal` (lista só de acréscimo, a mesma que a API
entrega por SSE). Este módulo lê essa lista, posta cada mensagem uma vez no Slack e
atualiza a mensagem quando a aprovação ou a suspeita muda de estado. Os cliques chamam os
mesmos métodos que a API usa (`aprovar`, `rejeitar`, `decidir_suspeita`), com as mesmas
regras. Falha do Slack só vira registro em `falhas`; o agente nunca para por causa dela.
"""

from __future__ import annotations

import logging
import re
import threading

from atendimento.agente.aprovacoes import AprovacaoRecusada
from atendimento.canal_slack.blocos import montar
from atendimento.canal_slack.config import ConfigSlack
from atendimento.privacidade import mascarar

logger = logging.getLogger("atendimento.canal_slack")

MAX_TENTATIVAS = 3
JUSTIFICATIVA_SUSPEITA = "decidido pelo Slack"
_PEDIDO = re.compile(r"\b(G[BC]H\d{6})\b", re.IGNORECASE)
_MUDA_POLITICA = re.compile(
    r"limite|alcada|alçada|politica|política|aument|liber[ae]|excec|exceç|sem aprova|"
    r"pode aprovar|aprova (direto|sozinho)",
    re.IGNORECASE,
)


def _motivo(erro: Exception) -> str:
    """Tipo do erro e, se houver, o código da API do Slack. Nunca o token."""
    resposta = getattr(erro, "response", None)
    codigo = None
    try:
        codigo = resposta.get("error") if resposta is not None else None
    except Exception:  # resposta sem .get
        codigo = None
    return f"{type(erro).__name__}" + (f" ({codigo})" if codigo else "")


class CanalSlack:
    def __init__(self, agente, cliente, config: ConfigSlack):
        self.agente = agente
        self.cliente = cliente
        self.config = config
        self.falhas: list[str] = []
        self._postadas: dict[str, dict] = {}  # id da mensagem do canal -> {ts, estado}
        self._tentativas: dict[str, int] = {}
        self._trava = threading.RLock()

    # ---------- espelho ----------

    def _estado(self, mensagem: dict) -> str | None:
        if mensagem.get("estado") is not None:
            return mensagem["estado"]
        aprovacao = getattr(self.agente, "aprovacoes", {}).get(mensagem.get("aprovacao_id"))
        return getattr(aprovacao, "estado", None)

    def _pendente(self, mensagem: dict) -> bool:
        return self._estado(mensagem) == "pendente"

    def _falhou(self, mid: str, erro: Exception) -> None:
        motivo = f"{mid}: {_motivo(erro)}"
        self.falhas.append(motivo)
        logger.warning("Slack: falha ao espelhar %s", motivo)

    def sincronizar(self) -> None:
        """Posta mensagens novas e atualiza as que mudaram de estado. Nunca levanta."""
        with self._trava:
            for mensagem in list(getattr(self.agente, "canal", [])):
                mid = mensagem.get("id")
                if not mid:
                    continue
                estado = self._estado(mensagem)
                postada = self._postadas.get(mid)
                try:
                    if postada is None:
                        if self._tentativas.get(mid, 0) >= MAX_TENTATIVAS:
                            continue
                        self._tentativas[mid] = self._tentativas.get(mid, 0) + 1
                        texto, blocos = montar(mensagem, pendente=estado == "pendente")
                        resposta = self.cliente.chat_postMessage(
                            channel=self.config.canal_id, text=texto, blocks=blocos
                        )
                        self._postadas[mid] = {"ts": resposta["ts"], "estado": estado}
                    elif estado != postada["estado"]:
                        desfecho = f"Situação: {estado}" if estado else None
                        texto, blocos = montar(mensagem, pendente=False, desfecho=desfecho)
                        self.cliente.chat_update(
                            channel=self.config.canal_id,
                            ts=postada["ts"],
                            text=texto,
                            blocks=blocos,
                        )
                        postada["estado"] = estado
                except Exception as erro:  # Slack fora do ar não derruba o agente
                    self._falhou(mid, erro)

    def _mensagem_por_ts(self, ts: str) -> dict | None:
        for mid, postada in self._postadas.items():
            if postada["ts"] == ts:
                return next((m for m in self.agente.canal if m.get("id") == mid), None)
        return None

    # ---------- botões ----------

    def _efemera(self, cliente, body: dict, texto: str) -> None:
        try:
            cliente.chat_postEphemeral(
                channel=body["channel"]["id"], user=body["user"]["id"], text=mascarar(texto)
            )
        except Exception as erro:
            self._falhou("efemera", erro)

    def ao_clicar(self, body: dict, cliente=None) -> None:
        """Clique em Aprovar/Rejeitar/Procedente/Improcedente."""
        cliente = cliente or self.cliente
        membro = body["user"]["id"]
        acao = body["actions"][0]
        action_id, valor = acao["action_id"], acao["value"]
        supervisor = self.config.supervisores.get(membro)
        if supervisor is None:
            self._efemera(
                cliente,
                body,
                "Você não está autorizado a decidir pelo Slack: seu usuário não está em "
                "SLACK_SUPERVISORES.",
            )
            return
        try:
            if action_id == "fio_aprovar":
                self.agente.aprovar(valor, supervisor, "aprovado pelo Slack")
                desfecho = f"Aprovado por {supervisor} pelo Slack."
            elif action_id == "fio_rejeitar":
                self.agente.rejeitar(valor, supervisor, f"rejeitado pelo Slack por {supervisor}")
                desfecho = f"Rejeitado por {supervisor} pelo Slack."
            elif action_id in ("fio_procedente", "fio_improcedente"):
                decisao = action_id.removeprefix("fio_")
                self.agente.decidir_suspeita(valor, supervisor, decisao, JUSTIFICATIVA_SUSPEITA)
                desfecho = f"Suspeita {valor} decidida como {decisao} por {supervisor}."
            else:
                return
        except KeyError:
            self._efemera(cliente, body, f"{valor} não existe mais no FIO.")
            return
        except (AprovacaoRecusada, PermissionError, ValueError) as erro:
            self._efemera(cliente, body, str(erro))
            return
        with self._trava:
            ts = body["message"]["ts"]
            mensagem = self._mensagem_por_ts(ts) or {"texto": "", "tipo": "aviso"}
            texto, blocos = montar(mensagem, pendente=False, desfecho=desfecho)
            try:
                cliente.chat_update(
                    channel=body["channel"]["id"], ts=ts, text=f"{desfecho} {texto}", blocks=blocos
                )
            except Exception as erro:
                self._falhou("atualizar", erro)
            for mid, postada in self._postadas.items():
                if postada["ts"] == ts:
                    m = next((x for x in self.agente.canal if x.get("id") == mid), None)
                    postada["estado"] = self._estado(m) if m else postada["estado"]

    # ---------- HG-10: pedido de colaborador ----------

    def responder_mencao(self, texto: str, usuario: str | None) -> str:
        """Pedido de colaborador (responder_colaborador). Não muda política nem alçada."""
        limpo = re.sub(r"<@[^>]+>", "", texto).strip()
        partes = []
        if _MUDA_POLITICA.search(limpo):
            partes.append(
                "Pedido de colaborador não muda política nem alçada "
                "(seguranca.acao_com_dinheiro_acima_do_limite_exige_aprovacao_humana). "
                "Para uma exceção, o caso precisa de aprovação do supervisor do turno."
            )
        base = getattr(self.agente, "base", None)
        for order_id in dict.fromkeys(p.upper() for p in _PEDIDO.findall(limpo)):
            pedido = base.pedido(order_id) if base is not None else None
            if pedido is None:
                partes.append(f"Pedido {order_id}: não encontrei na base.")
            else:
                entrega = (
                    pedido.data_entrega.strftime("%d/%m/%Y")
                    if pedido.data_entrega
                    else "sem entrega registrada"
                )
                partes.append(
                    f"Pedido {order_id}: status {pedido.status_entrega}; entrega: {entrega}."
                )
        if not partes:
            partes.append(
                "Posso informar o status de um pedido (me mande o número, ex.: GBH123456). "
                "Aprovações e suspeitas chegam aqui com botões para o supervisor."
            )
        return mascarar(" ".join(partes))

    def ao_mencionar(self, event: dict, say) -> None:
        try:
            resposta = self.responder_mencao(event.get("text", ""), event.get("user"))
            say(text=resposta, thread_ts=event.get("thread_ts") or event.get("ts"))
        except Exception as erro:
            self._falhou("mencao", erro)
