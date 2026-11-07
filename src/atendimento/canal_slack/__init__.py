"""Canal do time no Slack (P5): espelho, botões de decisão e pedidos de colaborador."""

from atendimento.canal_slack.canal import CanalSlack
from atendimento.canal_slack.conexao import ConexaoSlack, iniciar, registrar_handlers
from atendimento.canal_slack.config import ConfigSlack, config_do_ambiente
from atendimento.canal_slack.gancho import GanchoSlack, criar_gancho, registro_para
from atendimento.canal_slack.registro import RegistroBanco, RegistroMemoria

__all__ = [
    "CanalSlack",
    "ConexaoSlack",
    "ConfigSlack",
    "GanchoSlack",
    "RegistroBanco",
    "RegistroMemoria",
    "config_do_ambiente",
    "criar_gancho",
    "iniciar",
    "registrar_handlers",
    "registro_para",
]
