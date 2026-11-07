"""Ligação com o Slack por Socket Mode (slack-bolt 1.30).

`SocketModeHandler.connect()` abre a conexão sem bloquear e `close()` a encerra
(slack_bolt/adapter/socket_mode/base_handler.py; guia:
https://docs.slack.dev/tools/bolt-python/concepts/socket-mode). Os listeners seguem
https://docs.slack.dev/tools/bolt-python/concepts/actions (`app.action`, `ack()` em até 3 s)
e https://docs.slack.dev/tools/bolt-python/concepts/event-listening (`app.event`).
O espelho roda numa thread de fundo que lê `agente.canal` a cada segundo, como o SSE da API.
"""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Mapping

from atendimento.canal_slack.canal import CanalSlack
from atendimento.canal_slack.config import config_do_ambiente

logger = logging.getLogger("atendimento.canal_slack")

INTERVALO_S = 1.0
ACOES = re.compile(r"^fio_(aprovar|rejeitar|procedente|improcedente)$")


def registrar_handlers(app, canal: CanalSlack) -> None:
    @app.action(ACOES)
    def clicar(ack, body, client):
        ack()  # o Slack exige resposta em até 3 s; a decisão vem depois
        try:
            canal.ao_clicar(body, client)
        except Exception as erro:
            canal._falhou("clique", erro)

    @app.event("app_mention")
    def mencionar(event, say):
        canal.ao_mencionar(event, say)


class ConexaoSlack:
    def __init__(self, canal: CanalSlack, handler):
        self.canal = canal
        self.handler = handler
        self._parar = threading.Event()
        self._thread = threading.Thread(target=self._laco, name="fio-slack-espelho", daemon=True)

    def _laco(self) -> None:
        # a conexão do Socket Mode (rede) acontece aqui, fora da subida da API
        try:
            self.handler.connect()
        except Exception as erro:  # sem Socket Mode não há botões; o espelho tenta mesmo assim
            self.canal._falhou("socket_mode", erro)
        while not self._parar.is_set():
            try:
                self.canal.sincronizar()
            except Exception as erro:  # nunca derruba a thread
                self.canal._falhou("laco", erro)
            self._parar.wait(INTERVALO_S)

    def iniciar(self) -> ConexaoSlack:
        self._thread.start()
        return self

    def parar(self) -> None:
        self._parar.set()
        self._thread.join(timeout=5)
        try:
            self.handler.close()
        except Exception as erro:
            self.canal._falhou("fechar", erro)


def criar_app_bolt(config):
    """App do Bolt sem chamada de rede na subida (token_verification_enabled=False: o token é
    conferido na primeira chamada, não no auth.test do construtor) e com retry de rate limit
    que respeita o Retry-After (slack_sdk RateLimitErrorRetryHandler; guia:
    https://docs.slack.dev/tools/python-slack-sdk/web#retryhandler)."""
    from slack_bolt import App
    from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler

    app = App(token=config.bot_token, token_verification_enabled=False)
    app.client.retry_handlers.append(RateLimitErrorRetryHandler(max_retry_count=3))
    return app


def iniciar(agente, ambiente: Mapping[str, str] | None = None) -> ConexaoSlack | None:
    """Liga o canal no Slack se `ATENDIMENTO_SLACK=1` e os tokens existem; senão, None."""
    config = config_do_ambiente(ambiente)
    if config is None:
        return None
    try:
        from slack_bolt.adapter.socket_mode import SocketModeHandler

        app = criar_app_bolt(config)
        canal = CanalSlack(agente, app.client, config)
        registrar_handlers(app, canal)
        handler = SocketModeHandler(app, config.app_token)  # conecta na thread de fundo
    except Exception as erro:  # token inválido, rede fora: o FIO segue sem Slack
        logger.warning("Slack não ligou: %s", type(erro).__name__)
        return None
    logger.info("Canal do time espelhado no Slack (canal %s)", config.canal_id)
    return ConexaoSlack(canal, handler).iniciar()
