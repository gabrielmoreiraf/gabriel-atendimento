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


def iniciar(agente, ambiente: Mapping[str, str] | None = None) -> ConexaoSlack | None:
    """Liga o canal no Slack se `ATENDIMENTO_SLACK=1` e os tokens existem; senão, None."""
    config = config_do_ambiente(ambiente)
    if config is None:
        return None
    try:
        from slack_bolt import App
        from slack_bolt.adapter.socket_mode import SocketModeHandler

        app = App(token=config.bot_token)
        canal = CanalSlack(agente, app.client, config)
        registrar_handlers(app, canal)
        handler = SocketModeHandler(app, config.app_token)
        handler.connect()
    except Exception as erro:  # token inválido, rede fora: o FIO segue sem Slack
        logger.warning("Slack não ligou: %s", type(erro).__name__)
        return None
    logger.info("Canal do time espelhado no Slack (canal %s)", config.canal_id)
    return ConexaoSlack(canal, handler).iniciar()
