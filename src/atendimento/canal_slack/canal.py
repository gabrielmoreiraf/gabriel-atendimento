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
from atendimento.canal_slack.registro import RegistroMemoria
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


# Categoria do leitor -> categoria de politicas.csv (as demais têm o mesmo nome).
_CATEGORIA_DA_POLITICA = {
    "rastreio": "onde_esta_pedido",
    "atraso": "atraso_entrega",
    "arrependimento": "arrependimento_cancelamento",
    "avaria": "avaria_vazamento",
}


# Só vai ao Slack o que pede alguém: aprovação (inclui o lembrete do vigia), suspeita,
# escalação (inclui reação adversa), incidente novo do analista e alerta de SLA. Execuções de
# rotina, "não repetido (HG-16)", resultados de decisão e "chamei o analista" sem incidente
# novo ficam só no canal do time do app.
_TIPOS_ACIONAVEIS = {"aprovacao", "suspeita", "escalacao"}
_INCIDENTE = re.compile(r"\bINC-\d{6}\b")


def deve_ir_ao_slack(mensagem: dict, incidentes_vistos: set[str]) -> bool:
    if mensagem.get("tipo") in _TIPOS_ACIONAVEIS:
        return True
    if str(mensagem.get("chave", "")).startswith("sla:"):
        return True
    incidente = mensagem.get("incidente_id") or next(
        iter(_INCIDENTE.findall(str(mensagem.get("texto", "")))), None
    )
    if incidente and not mensagem.get("aprovacao_id") and not mensagem.get("suspeita_id"):
        if incidente in incidentes_vistos:
            return False
        incidentes_vistos.add(incidente)
        return True
    return False


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


class _IncidentesVistos:
    """Conjunto de incidentes já anunciados, guardado no registro (sobrevive à requisição)."""

    def __init__(self, registro):
        self.registro = registro

    def __contains__(self, incidente_id: str) -> bool:
        return self.registro.incidente_visto(incidente_id)

    def add(self, incidente_id: str) -> None:
        self.registro.marcar_incidente(incidente_id)


class CanalSlack:
    def __init__(
        self,
        agente,
        cliente,
        config: ConfigSlack,
        *,
        registro=None,
        observar_rodadas: bool = True,
    ):
        self.agente = agente
        self.cliente = cliente
        self.config = config
        self.registro = registro if registro is not None else RegistroMemoria()
        self.falhas: list[str] = []
        self._tentativas: dict[str, int] = {}
        self._ignoradas: set[str] = set()  # mensagens que ficam só no app
        self._incidentes = _IncidentesVistos(self.registro)
        self._rodada_terminando = False
        self._trava = threading.RLock()
        if observar_rodadas:  # Socket Mode; no modo HTTP quem avisa é o gancho
            self._observar_rodadas()

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

    def publicar(self, mensagem: dict) -> bool:
        """Posta a mensagem se for nova e acionável, ou atualiza (chat_update) a já postada se
        o estado mudou. Nunca levanta. Devolve False se o Slack pediu para esperar (rate limit).
        É o que o gancho do modo HTTP chama logo depois de gravar a mensagem do canal."""
        mid = mensagem.get("id")
        if not mid or mid in self._ignoradas:
            return True
        with self._trava:
            postada = self.registro.mensagem(mid)
            if postada is None and mid not in self._tentativas:
                if not deve_ir_ao_slack(mensagem, self._incidentes):
                    self._ignoradas.add(mid)
                    return True
            estado = self._estado(mensagem)
            try:
                if postada is None:
                    if self._tentativas.get(mid, 0) >= MAX_TENTATIVAS:
                        return True
                    self._tentativas[mid] = self._tentativas.get(mid, 0) + 1
                    texto, blocos = montar(mensagem, pendente=estado == "pendente")
                    resposta = self.cliente.chat_postMessage(
                        channel=self.config.canal_id, text=texto, blocks=blocos
                    )
                    self.registro.salvar_mensagem(mid, resposta["ts"], estado)
                elif estado != postada["estado"]:
                    desfecho = f"Situação: {estado}" if estado else None
                    texto, blocos = montar(mensagem, pendente=False, desfecho=desfecho)
                    self.cliente.chat_update(
                        channel=self.config.canal_id, ts=postada["ts"], text=texto, blocks=blocos
                    )
                    self.registro.salvar_mensagem(mid, postada["ts"], estado)
            except Exception as erro:  # Slack fora do ar não derruba o agente
                self._falhou(mid, erro)
                if _limitado(erro):  # respeita o limite: devolve a vez
                    self._tentativas[mid] = max(0, self._tentativas.get(mid, 1) - 1)
                    return False
            return True

    def sincronizar(self) -> None:
        """Socket Mode: percorre o canal do time, publica e, no fim da rodada, o resumo."""
        with self._trava:
            for mensagem in list(getattr(self.agente, "canal", [])):
                if not self.publicar(mensagem):
                    break  # rate limit: para esta volta
            self._resumir_rodada()

    # ---------- resumo por rodada (HP-09) ----------

    def _observar_rodadas(self) -> None:
        """Marca o fim de cada rodada pelo retorno de `processar_fila` (o evento `leitura` do
        barramento também sai quando uma conversa é processada sozinha, então não serve)."""
        original = getattr(self.agente, "processar_fila", None)
        if original is None:
            return

        def processar_fila(*args, **kwargs):
            placar = original(*args, **kwargs)
            self._rodada_terminando = True
            return placar

        self.agente.processar_fila = processar_fila

    def _resumir_rodada(self) -> None:
        """Uma mensagem por rodada da fila, depois das acionáveis da rodada. Rodada sem
        novidade (placar igual ao último resumo) não repete a mensagem."""
        if not self._rodada_terminando:
            return
        self._rodada_terminando = False
        if not self.postar_resumo(self.agente.placar()):
            self._rodada_terminando = True  # tenta de novo na próxima volta

    def postar_resumo(self, placar: dict) -> bool:
        """Uma mensagem com o placar da rodada; não repete placar igual ao último. Devolve
        False só se o Slack falhou (para tentar de novo)."""
        placar = {k: v for k, v in placar.items() if k != "replay"}
        if placar == self.registro.ultimo_placar():
            return True
        texto = self._texto_resumo(placar)
        try:
            self.cliente.chat_postMessage(
                channel=self.config.canal_id,
                text=texto,
                blocks=[
                    {"type": "section", "text": {"type": "mrkdwn", "text": texto}},
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"Detalhe no painel: {self.config.painel_url}",
                            }
                        ],
                    },
                ],
            )
            self.registro.salvar_placar(placar)
            return True
        except Exception as erro:
            self._falhou("resumo", erro)
            return False

    def _texto_resumo(self, placar: dict) -> str:
        hora = self.agente.agora.strftime("%H:%M")
        partes = [
            f"{placar.get('resolvidas_sozinho', 0)} resolvidas sozinho",
            f"{placar.get('aguardando_cliente', 0)} aguardando cliente",
            f"{placar.get('aguardando_aprovacao', 0)} aguardando aprovação",
        ]
        if placar.get("suspeitas"):
            partes.append(f"{placar['suspeitas']} suspeitas")
        partes += [
            f"{placar.get('escaladas', 0)} escaladas",
            f"{_rs(float(placar.get('custo_evitado_rs', 0)))} de custo evitado",
        ]
        return f"Rodada das {hora}: " + " · ".join(partes)

    def _mensagem_por_ts(self, ts: str) -> dict | None:
        mid = self.registro.mensagem_por_ts(ts)
        if mid is None:
            return None
        return next((m for m in getattr(self.agente, "canal", []) if m.get("id") == mid), None)

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
            self._efemera(cliente, body, f"{valor} não existe mais no Gabriel.")
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
            mid = self.registro.mensagem_por_ts(ts)
            if mid is not None:
                m = next((x for x in getattr(self.agente, "canal", []) if x.get("id") == mid), None)
                if m is not None:
                    self.registro.salvar_mensagem(mid, ts, self._estado(m))

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
                "pedido no Gabriel. Nada foi executado: conferir pelo fluxo normal do cliente.",
                None,
            )
            return (
                f"Pedido {order_id}: não encontrei atendimento aberto no Gabriel para {o_que}. "
                "Nada foi executado; escalei para o supervisor seguir pelo fluxo do cliente."
            )
        cid = caso.conversation_id
        # A categoria do caso vale para o pedido do colaborador: acoes_permitidas, caso
        # sensível e prazo (EC-03) continuam valendo. Sem categoria da política, escala.
        categoria = _CATEGORIA_DA_POLITICA.get(caso.categoria or "", caso.categoria)
        if not categoria or f"categorias.{categoria}.acoes_permitidas" not in self.agente.politicas:
            self._escalar(
                f"{cid}: {origem}: {o_que}. O atendimento não tem categoria da política "
                f"({caso.categoria or 'sem categoria'}) para conferir a ação: decisão de uma pessoa.",
                cid,
            )
            return (
                f"{o_que}: o atendimento {cid} não tem categoria da política que permita "
                "conferir essa ação. Nada foi executado; escalei para o supervisor."
            )
        acao = AcaoProposta(
            ferramenta=ferramenta,
            papel=Papel.ATENDENTE,
            executado_por=EXECUTOR,
            conversation_id=cid,
            order_id=order_id,
            valor_rs=valor,
            motivo=origem,
            categoria=categoria,
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
            efeito = "negado" if decisao.resultado is Resultado.NEGAR else "não executado"
            return (
                f"{o_que}: {efeito} pela política ({decisao.regra}). {decisao.motivo} "
                "Pedido de colaborador não muda a política; escalei para o supervisor."
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
