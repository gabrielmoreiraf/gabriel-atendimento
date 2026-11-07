"""Verificador de evidência (W3): responde "a reclamação procede?" com fatos verificáveis."""

from atendimento.verificacao.evidencia import (
    CUSTO_SINALIZAR_VERDADEIRO_RS,
    FATOR_CUSTO_ACEITAR_FALSO,
    LIMIAR_REENVIOS,
    SINAIS_DE_CONTEXTO,
    SINAIS_FORTES,
    verificar,
)

__all__ = [
    "CUSTO_SINALIZAR_VERDADEIRO_RS",
    "FATOR_CUSTO_ACEITAR_FALSO",
    "LIMIAR_REENVIOS",
    "SINAIS_DE_CONTEXTO",
    "SINAIS_FORTES",
    "verificar",
]
