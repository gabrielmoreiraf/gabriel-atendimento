"""Entrypoint da API no Vercel (ADR-002): expõe `atendimento.api.app:app`.

O projeto usa layout `src/` sem pacote instalável; aqui só pomos `src/` no caminho de
importação. Toda a lógica continua em `src/atendimento`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from atendimento.api.app import app  # noqa: E402

__all__ = ["app"]
