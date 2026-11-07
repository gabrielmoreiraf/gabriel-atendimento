"""Configuração do canal no Slack, lida do ambiente (`.env.example`).

Liga só com `ATENDIMENTO_SLACK=1` e todos os tokens presentes. Os tokens ficam fora do
`repr` e nunca vão para log.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConfigSlack:
    bot_token: str = field(repr=False)
    app_token: str = field(repr=False)
    canal_id: str
    supervisores: dict[str, str]  # member ID do Slack -> colaborador_id
    painel_url: str = "http://localhost:5173"  # link do resumo da rodada para o detalhe
    # ADR-002: "http" no Vercel (endpoint assinado, sem thread), "socket" no uso local
    modo: str = "socket"
    signing_secret: str = field(default="", repr=False)


def _supervisores(valor: str) -> dict[str, str]:
    mapa = {}
    for par in valor.split(","):
        membro, _, colaborador = par.strip().partition(":")
        if membro.strip() and colaborador.strip():
            mapa[membro.strip()] = colaborador.strip()
    return mapa


def config_do_ambiente(ambiente: Mapping[str, str] | None = None) -> ConfigSlack | None:
    ambiente = os.environ if ambiente is None else ambiente
    if ambiente.get("ATENDIMENTO_SLACK", "0").strip() != "1":
        return None
    modo = ambiente.get("ATENDIMENTO_SLACK_MODO", "").strip().lower() or (
        "http" if ambiente.get("VERCEL") else "socket"
    )
    if modo not in ("http", "socket"):
        return None
    bot = ambiente.get("SLACK_BOT_TOKEN", "").strip()
    app = ambiente.get("SLACK_APP_TOKEN", "").strip()
    segredo = ambiente.get("SLACK_SIGNING_SECRET", "").strip()
    canal = ambiente.get("SLACK_CANAL_ID", "").strip()
    # socket: App-Level Token (xapp) para o WebSocket; http: Signing Secret para a assinatura
    if not (bot and canal and (app if modo == "socket" else segredo)):
        return None
    return ConfigSlack(
        bot_token=bot,
        app_token=app,
        modo=modo,
        signing_secret=segredo,
        canal_id=canal,
        supervisores=_supervisores(ambiente.get("SLACK_SUPERVISORES", "")),
        painel_url=ambiente.get("ATENDIMENTO_PAINEL_URL", "").strip() or "http://localhost:5173",
    )
