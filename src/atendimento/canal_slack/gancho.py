"""Gancho do modo HTTP (ADR-002): sem thread, o Slack é atualizado na mesma requisição que
grava a mensagem do canal do time.

Contrato com o estado do agente (W4): depois de gravar ou atualizar uma mensagem do canal,
chamar `gancho.mensagem_gravada(mensagem)`; ao fim de `processar_fila`, chamar
`gancho.rodada_terminada(placar)`. Os dois nunca levantam (falha do Slack só vira registro).
O `ts` de cada mensagem postada fica no banco (`RegistroBanco`) quando o agente tem `banco`.
"""

from __future__ import annotations

from collections.abc import Mapping

from atendimento.canal_slack.canal import CanalSlack
from atendimento.canal_slack.config import ConfigSlack, config_do_ambiente
from atendimento.canal_slack.registro import RegistroBanco, RegistroMemoria

_REGISTRO_DO_PROCESSO = RegistroMemoria()


def registro_para(agente):
    """No banco quando o agente tem `banco` (Vercel/Neon); senão, na memória do processo."""
    banco = getattr(agente, "banco", None) or getattr(getattr(agente, "base", None), "banco", None)
    if banco is None or not hasattr(banco, "executar"):
        return _REGISTRO_DO_PROCESSO
    return RegistroBanco(banco)


def cliente_web(config: ConfigSlack):
    """WebClient sem chamada de rede na criação e com retry de rate limit (Retry-After)."""
    from slack_sdk import WebClient
    from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler

    cliente = WebClient(token=config.bot_token)
    cliente.retry_handlers.append(RateLimitErrorRetryHandler(max_retry_count=3))
    return cliente


class GanchoSlack:
    def __init__(self, canal: CanalSlack):
        self.canal = canal

    def mensagem_gravada(self, mensagem: dict) -> None:
        try:
            self.canal.publicar(mensagem)
        except Exception as erro:  # nunca derruba a requisição do agente
            self.canal._falhou("gancho", erro)

    def rodada_terminada(self, placar: dict) -> None:
        try:
            self.canal.postar_resumo(placar)
        except Exception as erro:
            self.canal._falhou("gancho_resumo", erro)


def criar_gancho(
    agente,
    *,
    ambiente: Mapping[str, str] | None = None,
    cliente=None,
    registro=None,
) -> GanchoSlack | None:
    """Gancho do modo HTTP; None se o Slack está desligado ou em Socket Mode (lá o espelho
    roda na thread de `conexao.iniciar`)."""
    config = config_do_ambiente(ambiente)
    if config is None or config.modo != "http":
        return None
    canal = CanalSlack(
        agente,
        cliente if cliente is not None else cliente_web(config),
        config,
        registro=registro if registro is not None else registro_para(agente),
        observar_rodadas=False,
    )
    return GanchoSlack(canal)
