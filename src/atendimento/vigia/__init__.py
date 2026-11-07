"""Colega que acompanha o dia e avisa o time sem ser perguntado (P1, HG-20, HG-21)."""

from atendimento.vigia.avisos import (
    JANELA_AVISO_SLA_MIN,
    LEMBRETE_APROVACAO_HORAS,
    AvisoSla,
    LembreteAprovacao,
    alertas_sla,
    lembretes_aprovacao,
    prazo_primeira_resposta,
)

__all__ = [
    "JANELA_AVISO_SLA_MIN",
    "LEMBRETE_APROVACAO_HORAS",
    "AvisoSla",
    "LembreteAprovacao",
    "alertas_sla",
    "lembretes_aprovacao",
    "prazo_primeira_resposta",
]
