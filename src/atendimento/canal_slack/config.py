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
    bot = ambiente.get("SLACK_BOT_TOKEN", "").strip()
    app = ambiente.get("SLACK_APP_TOKEN", "").strip()
    canal = ambiente.get("SLACK_CANAL_ID", "").strip()
    if not (bot and app and canal):
        return None
    return ConfigSlack(
        bot_token=bot,
        app_token=app,
        canal_id=canal,
        supervisores=_supervisores(ambiente.get("SLACK_SUPERVISORES", "")),
    )
