"""Apoio aos testes `-m postgres`: Banco no Neon num esquema temporário.

A `DATABASE_URL` vem do ambiente ou do `.env.local`; nunca é impressa. Cada uso cria um
esquema `teste_<aleatório>`, aponta o `search_path` para ele e o apaga no fim, sem tocar nas
tabelas carregadas da base.
"""

from __future__ import annotations

import os
import secrets
from contextlib import contextmanager
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]


def url_postgres() -> str | None:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    arquivo = RAIZ / ".env.local"
    if not arquivo.exists():
        return None
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        chave, _, valor = linha.partition("=")
        if chave.strip() == "DATABASE_URL":
            return valor.strip().strip('"').strip("'") or None
    return None


@contextmanager
def banco_postgres_temporario():
    from atendimento.dados.banco import conectar

    url = url_postgres()
    if not url:
        pytest.skip("sem DATABASE_URL (ambiente ou .env.local)")
    esquema = f"teste_{secrets.token_hex(4)}"
    banco = conectar(url, esquema=esquema)
    try:
        yield banco
    finally:
        banco.executar(f'DROP SCHEMA IF EXISTS "{esquema}" CASCADE')
        banco.fechar()
