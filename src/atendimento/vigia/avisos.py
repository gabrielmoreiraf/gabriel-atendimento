"""Colega que acompanha o dia e avisa o time sem ser perguntado (P1, HG-20, HG-21).

Limiares (Q9 de REQUISITOS.md, ponto de partida aceito para a PoC):
- SLA: avisa quando faltam até `JANELA_AVISO_SLA_MIN` = 10 min para vencer a 1ª resposta,
  e avisa também o que já venceu. Na fila real às 08:00 de 02/11 saem 2 avisos: o e-mail
  já fora do SLA (M5) e o WhatsApp AT116664, que vence às 08:08:52. Às 08:20 aparecem as 18
  conversas de WhatsApp sem 1ª resposta (M5): 16 vencem às 08:30, AT116666 às 08:26:45 e
  AT116664 já venceu.
- Aprovação: lembra o supervisor depois de `LEMBRETE_APROVACAO_HORAS` = 2 h sem resposta e,
  a cada 2 h seguintes, chama outro supervisor do turno que não seja o autor; o prazo é o de
  `reclamacao_suspeita.prazo_decisao_horas` (24 h).

Prazos de 1ª resposta vêm de `politicas.sla_primeira_resposta`: WhatsApp em minutos contados
só no horário humano (`horario_atendimento_humano`), e-mail e Reclame Aqui em horas corridas.
Funções puras: recebem linhas da base e devolvem avisos com texto neutro, sem dado pessoal.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from atendimento.contratos import AGORA, FUSO
from atendimento.politicas import supervisor_no_turno

JANELA_AVISO_SLA_MIN = 10  # Q9
LEMBRETE_APROVACAO_HORAS = 2  # Q9
MENSAGEM_CLIENTE_EM_ANALISE = (
    "Seu caso segue em análise com o nosso time. Assim que houver uma decisão, "
    "você recebe o retorno por aqui."
)


@dataclass(frozen=True)
class AvisoSla:
    conversation_id: str
    canal: str
    prazo: datetime
    minutos_restantes: float  # negativo = já estourou (minutos do horário humano no WhatsApp)
    situacao: str  # vai_estourar, estourado
    para: str | None  # atendente da conversa; None = time de atendimento
    texto: str

    @property
    def chave(self) -> str:
        return f"sla:{self.conversation_id}:{self.situacao}"


@dataclass(frozen=True)
class LembreteAprovacao:
    aprovacao_id: str
    solicitado_em: datetime
    prazo: datetime
    horas_paradas: float
    nivel: int  # 1 = primeiro lembrete; 2+ = chama outro supervisor
    vencido: bool
    para: str | None  # supervisor no turno; None = fora do horário (fila para a abertura)
    texto: str
    conversation_id: str | None = None
    mensagem_cliente: str = MENSAGEM_CLIENTE_EM_ANALISE  # HG-21 / Q9: sem prometer resultado

    @property
    def chave(self) -> str:
        return f"aprovacao:{self.aprovacao_id}:{self.nivel}"


def _data_hora(valor: str) -> datetime:
    return datetime.fromisoformat(valor).replace(tzinfo=FUSO)


def _hora(valor: str) -> int:
    return int(valor.split(":")[0])


def _janela(politicas: dict[str, str]) -> tuple[int, int]:
    return (
        _hora(politicas.get("horario_atendimento_humano.inicio", "08:00")),
        _hora(politicas.get("horario_atendimento_humano.fim", "20:00")),
    )


def _somar_minutos_comerciais(inicio: datetime, minutos: float, h_ini: int, h_fim: int) -> datetime:
    cursor, restante = inicio, minutos
    while True:
        abre = cursor.replace(hour=h_ini, minute=0, second=0, microsecond=0)
        fecha = cursor.replace(hour=h_fim, minute=0, second=0, microsecond=0)
        if cursor < abre:
            cursor = abre
        if cursor >= fecha:
            cursor = abre + timedelta(days=1)
            continue
        disponivel = (fecha - cursor).total_seconds() / 60
        if restante <= disponivel:
            return cursor + timedelta(minutes=restante)
        restante -= disponivel
        cursor = abre + timedelta(days=1)


def _minutos_comerciais(inicio: datetime, fim: datetime, h_ini: int, h_fim: int) -> float:
    """Minutos entre inicio e fim só no horário humano (mesma regra do baseline, M5)."""
    if fim < inicio:
        return -_minutos_comerciais(fim, inicio, h_ini, h_fim)
    total, cursor = 0.0, inicio
    while cursor < fim:
        abre = cursor.replace(hour=h_ini, minute=0, second=0, microsecond=0)
        fecha = cursor.replace(hour=h_fim, minute=0, second=0, microsecond=0)
        a, b = max(cursor, abre), min(fim, fecha)
        if b > a:
            total += (b - a).total_seconds() / 60
        cursor = (cursor + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return total


def _so_horario_comercial(canal: str, politicas: dict[str, str]) -> bool:
    chave = f"sla_primeira_resposta.{canal}.conta_apenas_horario_comercial"
    return politicas.get(chave, "False") == "True"


def prazo_primeira_resposta(conversa: dict, politicas: dict[str, str]) -> datetime | None:
    canal = conversa["canal"]
    abertura = _data_hora(conversa["data_abertura"])
    if f"sla_primeira_resposta.{canal}.minutos" in politicas:
        minutos = float(politicas[f"sla_primeira_resposta.{canal}.minutos"])
        if _so_horario_comercial(canal, politicas):
            return _somar_minutos_comerciais(abertura, minutos, *_janela(politicas))
        return abertura + timedelta(minutes=minutos)
    if f"sla_primeira_resposta.{canal}.horas" in politicas:
        return abertura + timedelta(hours=float(politicas[f"sla_primeira_resposta.{canal}.horas"]))
    return None


def alertas_sla(
    fila: list[dict],
    politicas: dict[str, str],
    agora: datetime = AGORA,
    *,
    janela_min: float = JANELA_AVISO_SLA_MIN,
) -> list[AvisoSla]:
    """HG-20: conversas sem 1ª resposta que vencem em até `janela_min` ou já venceram."""
    avisos = []
    for conversa in fila:
        if conversa.get("data_primeira_resposta"):
            continue
        prazo = prazo_primeira_resposta(conversa, politicas)
        if prazo is None:
            continue
        canal = conversa["canal"]
        if _so_horario_comercial(canal, politicas):
            restantes = _minutos_comerciais(agora, prazo, *_janela(politicas))
        else:
            restantes = (prazo - agora).total_seconds() / 60
        if restantes > janela_min:
            continue
        cid = conversa["conversation_id"]
        quando = prazo.strftime("%d/%m %H:%M")
        if restantes > 0:
            situacao = "vai_estourar"
            texto = (
                f"Conversa {cid} ({canal}) ainda sem 1ª resposta: o SLA vence às {quando}, "
                f"faltam {restantes:.0f} min. Impacto: fura o SLA de 1ª resposta. "
                "Precisa de alguém do atendimento respondendo agora."
            )
        else:
            situacao = "estourado"
            texto = (
                f"Conversa {cid} ({canal}) passou do SLA de 1ª resposta, que venceu às "
                f"{quando} (há {-restantes:.0f} min). Impacto: cliente esperando além do "
                "prometido. Precisa de resposta prioritária do atendimento."
            )
        avisos.append(
            AvisoSla(
                conversation_id=cid,
                canal=canal,
                prazo=prazo,
                minutos_restantes=round(restantes, 1),
                situacao=situacao,
                para=conversa.get("atendente_id") or None,
                texto=texto,
            )
        )
    return sorted(avisos, key=lambda a: (a.minutos_restantes, a.conversation_id))


def lembretes_aprovacao(
    pendentes: list[dict],
    agora: datetime = AGORA,
    *,
    equipe: list[dict],
    politicas: dict[str, str],
    intervalo_horas: float = LEMBRETE_APROVACAO_HORAS,
) -> list[LembreteAprovacao]:
    """HG-21: aprovações pendentes há `intervalo_horas` ou mais viram lembrete ao supervisor.

    `pendentes`: linhas da tabela `aprovacoes` (W1), com `acao` em JSON e `solicitado_em`.
    Nível 1 vai ao supervisor do turno; do nível 2 em diante, a outro supervisor do turno,
    nunca o autor da ação (solicitante ou executor).
    """
    prazo_horas = float(politicas.get("reclamacao_suspeita.prazo_decisao_horas", "24"))
    abertura = politicas.get("horario_atendimento_humano.inicio", "08:00")
    lembretes = []
    for aprovacao in pendentes:
        if aprovacao.get("estado", "pendente") != "pendente":
            continue
        solicitado_em = _data_hora(aprovacao["solicitado_em"])
        horas = (agora - solicitado_em).total_seconds() / 3600
        if horas < intervalo_horas:
            continue
        nivel = int(horas // intervalo_horas)
        acao = json.loads(aprovacao.get("acao") or "{}")
        autores = {aprovacao.get("solicitado_por"), acao.get("executado_por")}
        candidatos = [p for p in equipe if p.get("colaborador_id") not in autores]
        primeiro = supervisor_no_turno(candidatos, agora)
        para = primeiro
        if nivel >= 2 and primeiro is not None:
            outros = [p for p in candidatos if p.get("colaborador_id") != primeiro]
            para = supervisor_no_turno(outros, agora) or primeiro
        prazo = solicitado_em + timedelta(hours=prazo_horas)
        vencido = agora > prazo
        aid = aprovacao["aprovacao_id"]
        o_que = f"{acao.get('ferramenta', 'ação')} no pedido {acao.get('order_id') or '-'}"
        situacao = (
            f"o prazo de {prazo_horas:.0f} h venceu em {prazo.strftime('%d/%m %H:%M')}"
            if vencido
            else f"prazo de decisão até {prazo.strftime('%d/%m %H:%M')}"
        )
        quem = (
            f"Precisa de decisão de {para}."
            if para
            else f"Nenhum supervisor no turno agora: fica na fila para as {abertura}."
        )
        texto = (
            f"Aprovação {aid} ({o_que}) parada há {horas:.1f} h; {situacao}. "
            f"Impacto: o cliente segue aguardando. {quem}"
        )
        lembretes.append(
            LembreteAprovacao(
                aprovacao_id=aid,
                solicitado_em=solicitado_em,
                prazo=prazo,
                horas_paradas=round(horas, 1),
                nivel=nivel,
                vencido=vencido,
                para=para,
                texto=texto,
                conversation_id=acao.get("conversation_id"),
            )
        )
    return lembretes
