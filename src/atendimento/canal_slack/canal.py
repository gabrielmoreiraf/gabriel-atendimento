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
import unicodedata
from contextlib import nullcontext

from atendimento.agente.aprovacoes import Aprovacao, AprovacaoInvalida, AprovacaoRecusada
from atendimento.agente.caso import EXECUTOR, RodadaEmAndamento
from atendimento.canal_slack.blocos import montar
from atendimento.canal_slack.config import ConfigSlack
from atendimento.contratos import AcaoProposta, Papel, Resultado
from atendimento.politicas import decidir
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
# HG-10: pedido de ação com dinheiro feito por colaborador (texto sem acento, minúsculo).
_ACOES_COM_DINHEIRO = (
    ("reembolsar", re.compile(r"reembols|estorn|devolv\w* o (dinheiro|valor)")),
    ("reimprimir_personalizacao", re.compile(r"reimprim|nova producao")),
    ("reenviar_produto", re.compile(r"reenvi|envia\w* de novo|manda\w* outr")),
    ("trocar_produto", re.compile(r"\btroc")),
)
_VALOR = re.compile(r"r\$\s*(\d[\d.]*(?:,\d{1,2})?)|(\d[\d.]*(?:,\d{1,2})?)\s*reais")


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto.lower()) if not unicodedata.combining(c)
    )


def _valor(texto: str) -> float | None:
    m = _VALOR.search(_PEDIDO.sub(" ", _sem_acento(texto)))
    if not m:
        return None
    bruto = (m.group(1) or m.group(2)).replace(".", "").replace(",", ".")
    return float(bruto)


def _rs(valor: float) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _limitado(erro: Exception) -> bool:
    """Rate limit do Slack (HTTP 429 / ratelimited): tenta de novo depois, sem perder a vez."""
    resposta = getattr(erro, "response", None)
    try:
        if resposta.get("error") == "ratelimited":
            return True
    except Exception:
        pass
    return getattr(resposta, "status_code", None) == 429


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
                    if _limitado(erro):  # respeita o limite: devolve a vez e para esta rodada
                        self._tentativas[mid] = max(0, self._tentativas.get(mid, 1) - 1)
                        break

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
        except (
            AprovacaoRecusada,
            AprovacaoInvalida,
            RodadaEmAndamento,
            PermissionError,
            ValueError,
        ) as erro:
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
        """Pedido de colaborador (HG-10). Não muda política nem alçada; a resposta vai para o
        log como `responder_colaborador`."""
        limpo = re.sub(r"<@[^>]+>", "", texto).strip()
        pedidos = list(dict.fromkeys(p.upper() for p in _PEDIDO.findall(limpo)))
        normal = _sem_acento(limpo)
        ferramenta = next((f for f, padrao in _ACOES_COM_DINHEIRO if padrao.search(normal)), None)
        valor = _valor(limpo)
        if ferramenta and pedidos and valor:
            resposta = mascarar(self._pedido_com_dinheiro(ferramenta, valor, pedidos[0], usuario))
        else:
            resposta = self._resposta_informativa(limpo, pedidos)
        self._registrar_resposta(resposta, pedidos[0] if pedidos else None)
        return resposta

    def _resposta_informativa(self, limpo: str, pedidos: list[str]) -> str:
        partes = []
        if _MUDA_POLITICA.search(limpo) or any(
            p.search(_sem_acento(limpo)) for _, p in _ACOES_COM_DINHEIRO
        ):
            partes.append(
                "Pedido de colaborador não muda política nem alçada "
                "(seguranca.acao_com_dinheiro_acima_do_limite_exige_aprovacao_humana). "
                "Para uma exceção, o caso precisa de aprovação do supervisor do turno."
            )
        base = getattr(self.agente, "base", None)
        for order_id in pedidos:
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

    def _caso_do_pedido(self, order_id: str):
        casos = getattr(self.agente, "casos", {}) or {}
        return next((c for c in casos.values() if getattr(c, "order_id", None) == order_id), None)

    def _escalar(self, texto: str, cid: str | None, para: str | None = None) -> None:
        self.agente.postar_no_canal("escalacao", para, texto, cid)

    def _pedido_com_dinheiro(
        self, ferramenta: str, valor: float, order_id: str, usuario: str | None
    ) -> str:
        """HG-10: pedido de colaborador passa pela política e nunca executa sozinho.
        Acima da alçada abre `solicitar_aprovacao` (botões no canal); dentro da alçada ou fora
        da política, escala para o fluxo normal do cliente."""
        quem = self.config.supervisores.get(usuario or "") or EXECUTOR
        origem = f"pedido de colaborador pelo Slack ({usuario or 'desconhecido'})"
        base = getattr(self.agente, "base", None)
        pedido = base.pedido(order_id) if base is not None else None
        caso = self._caso_do_pedido(order_id)
        o_que = f"{ferramenta} de {_rs(valor)} no pedido {order_id}"
        if pedido is None or caso is None:
            self._escalar(
                f"Colaborador pediu {o_que} pelo Slack, mas não há atendimento aberto para esse "
                "pedido no FIO. Nada foi executado: conferir pelo fluxo normal do cliente.",
                None,
            )
            return (
                f"Pedido {order_id}: não encontrei atendimento aberto no FIO para {o_que}. "
                "Nada foi executado; escalei para o supervisor seguir pelo fluxo do cliente."
            )
        cid = caso.conversation_id
        # categoria=None: o pedido do colaborador não é a reclamação classificada do cliente;
        # vale a alçada da política, e nada executa sem uma pessoa.
        acao = AcaoProposta(
            ferramenta=ferramenta,
            papel=Papel.ATENDENTE,
            executado_por=EXECUTOR,
            conversation_id=cid,
            order_id=order_id,
            valor_rs=valor,
            motivo=origem,
        )
        with getattr(self.agente, "_trava", None) or nullcontext():
            anteriores = (
                base.acoes_com_dinheiro(order_id) if hasattr(base, "acoes_com_dinheiro") else []
            )
            decisao = decidir(
                acao,
                pedido=pedido,
                acoes_anteriores=anteriores,
                politicas=self.agente.politicas,
                equipe=self.agente.equipe,
                agora=self.agente.agora,
            )
            if decisao.resultado is Resultado.PEDIR_APROVACAO:
                registro = self.agente.executar(
                    caso,
                    AcaoProposta(
                        ferramenta="solicitar_aprovacao",
                        papel=Papel.ATENDENTE,
                        executado_por=EXECUTOR,
                        conversation_id=cid,
                        order_id=order_id,
                        valor_rs=valor,
                        motivo=f"{ferramenta}: {decisao.motivo} ({origem})",
                    ),
                    acao_pendente=acao,
                )
                aprovacao_id = registro.referencia_sistema
                self.agente.aprovacoes[aprovacao_id] = Aprovacao(
                    aprovacao_id=aprovacao_id,
                    acao=acao,
                    solicitado_por=quem,
                    aprovador_sugerido=decisao.aprovador_sugerido,
                )
                caso.aprovacao_ids.append(aprovacao_id)
                self.agente.postar_no_canal(
                    "aprovacao",
                    decisao.aprovador_sugerido,
                    f"{cid}: {origem}: {o_que}. {decisao.motivo}",
                    cid,
                    aprovacao_id=aprovacao_id,
                    estado="pendente",
                    solicitado_por=quem,
                )
                return (
                    f"{o_que} exige aprovação ({decisao.regra}): abri a solicitação "
                    f"{aprovacao_id} para {decisao.aprovador_sugerido or 'o supervisor do turno'}. "
                    "Nada foi executado; pedido de colaborador não muda a política."
                )
            if decisao.resultado is Resultado.EXECUTAR:
                self._escalar(
                    f"{cid}: {origem}: {o_que}. Cabe na alçada, mas pedido de colaborador não "
                    "executa sozinho: conferir pelo fluxo normal do cliente.",
                    cid,
                    decisao.aprovador_sugerido,
                )
                return (
                    f"{o_que} cabe na alçada, mas pedido de colaborador não executa sozinho: "
                    "vai pelo fluxo normal do cliente. Escalei para o supervisor; nada foi executado."
                )
            self._escalar(
                f"{cid}: {origem}: {o_que}. Política: {decisao.motivo} ({decisao.regra}).",
                cid,
                decisao.aprovador_sugerido,
            )
            return (
                f"Pela política ({decisao.regra}): {decisao.motivo} Não executei {o_que}; "
                "escalei para o supervisor."
            )

    def _registrar_resposta(self, resposta: str, order_id: str | None) -> None:
        ferramentas = getattr(self.agente, "ferramentas", None)
        if ferramentas is None:
            return
        try:
            ferramentas.executar(
                AcaoProposta(
                    ferramenta="responder_colaborador",
                    papel=Papel.ATENDENTE,
                    executado_por=EXECUTOR,
                    order_id=order_id,
                    motivo=resposta,
                )
            )
        except Exception as erro:  # o log não pode impedir a resposta no Slack
            self._falhou("responder_colaborador", erro)

    def ao_mencionar(self, event: dict, say) -> None:
        try:
            resposta = self.responder_mencao(event.get("text", ""), event.get("user"))
            say(text=resposta, thread_ts=event.get("thread_ts") or event.get("ts"))
        except Exception as erro:
            self._falhou("mencao", erro)
