"""Slack em modo HTTP (ADR-002): `POST /api/slack/eventos` recebe eventos e interatividade.

A assinatura (`SLACK_SIGNING_SECRET`) é verificada pelo Bolt antes de qualquer listener, e
`process_before_response=True` roda o listener dentro da requisição (modelo FaaS do Vercel):
https://docs.slack.dev/tools/bolt-python/concepts/lazy-listeners (FaaS) e o adaptador
`slack_bolt.adapter.fastapi.SlackRequestHandler`. Este endpoint fica fora da senha da demo:
quem autentica é a assinatura do Slack.

Plugar no app: `app.include_router(criar_router(ag))`, em que `ag()` devolve o Agente.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from atendimento.canal_slack import CanalSlack, config_do_ambiente, registrar_handlers
from atendimento.canal_slack.gancho import cliente_web, registro_para


def _app_bolt(config, obter_agente: Callable[[], Any], cliente=None):
    from slack_bolt import App

    slack = cliente if cliente is not None else cliente_web(config)
    app = App(
        client=slack,
        signing_secret=config.signing_secret,
        process_before_response=True,
        token_verification_enabled=False,
    )

    def canal() -> CanalSlack:
        agente = obter_agente()
        return CanalSlack(
            agente, slack, config, registro=registro_para(agente), observar_rodadas=False
        )

    registrar_handlers(app, canal, cliente_do_canal=True)
    return app


def criar_router(obter_agente: Callable[[], Any], *, cliente=None) -> APIRouter:
    router = APIRouter(tags=["slack"])
    cache: dict[str, Any] = {}

    @router.post("/api/slack/eventos")
    async def eventos(request: Request):
        config = config_do_ambiente()
        if config is None or config.modo != "http":
            raise HTTPException(404, "Slack em modo HTTP desligado")
        # um App do Bolt por configuração (o processo do Vercel é reaproveitado entre chamadas)
        chave = (config.canal_id, hash(config.signing_secret), hash(config.bot_token))
        if cache.get("chave") != chave:
            from slack_bolt.adapter.fastapi import SlackRequestHandler

            cache["chave"] = chave
            cache["handler"] = SlackRequestHandler(_app_bolt(config, obter_agente, cliente))
        return await cache["handler"].handle(request)

    return router
