"""Entrypoint do Vercel (ADR-002): `servidor_vercel:app` precisa importar sem `PYTHONPATH`.

O Vercel carrega o arquivo da raiz com o pacote em `src/` não instalado; o teste roda o import
num processo limpo, como a função faz, e confere que o app é o mesmo FastAPI do projeto.
"""

import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def test_HG_13_entrypoint_vercel_importa_sem_pythonpath():
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    codigo = (
        "import servidor_vercel, atendimento.api.app as m;"
        "assert servidor_vercel.app is m.app;"
        "rotas = {getattr(r, 'path', '') for r in servidor_vercel.app.routes};"
        "assert {'/api/fila', '/api/eventos'} <= rotas, rotas;"
        "print('ok')"
    )
    saida = subprocess.run(
        [sys.executable, "-c", codigo], cwd=RAIZ, env=env, capture_output=True, text=True
    )
    assert saida.returncode == 0, saida.stderr[-2000:]
    assert saida.stdout.strip().endswith("ok")
