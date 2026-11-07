"""Canal do time no Slack (P5): espelho, botões de decisão e pedidos de colaborador."""

from atendimento.canal_slack.canal import CanalSlack
from atendimento.canal_slack.conexao import ConexaoSlack, iniciar, registrar_handlers
from atendimento.canal_slack.config import ConfigSlack, config_do_ambiente

__all__ = [
    "CanalSlack",
    "ConexaoSlack",
    "ConfigSlack",
    "config_do_ambiente",
    "iniciar",
    "registrar_handlers",
]
