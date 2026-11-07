"""Diagnóstico do deploy: GET /api/saude diz o que está ligado, sem expor segredos.

No Vercel as variáveis são sensíveis e não dá para ler os valores; o endpoint mostra o efeito
delas (leitor ativo, Slack, origem da base) e quantas falhas houve.
"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

import atendimento.api.app as modulo
from atendimento.dados.carga import carregar

FIXTURES = Path(__file__).parent / "fixtures" / "dados"


def _cliente(tmp_path, monkeypatch, **env):
    pronta = tmp_path / "pronta.db"
    carregar(FIXTURES, pronta)
    monkeypatch.setenv("ATENDIMENTO_BASE_PRONTA", str(pronta))
    monkeypatch.setenv("ATENDIMENTO_DB", str(tmp_path / "atendimento.db"))
    for chave, valor in env.items():
        monkeypatch.setenv(chave, valor)
    return TestClient(modulo.criar_app())


def test_saude_com_regras_e_sem_slack(tmp_path, monkeypatch):
    monkeypatch.setenv("ATENDIMENTO_SLACK", "0")  # o .env local não religa o Slack
    cliente = _cliente(tmp_path, monkeypatch, ATENDIMENTO_LLM="0")

    saude = cliente.get("/api/saude").json()

    assert saude["leitor"] == "regras"
    assert saude["base"] == "pronta"
    assert saude["slack"] is None


def test_saude_mostra_o_leitor_com_claude_e_as_falhas(tmp_path, monkeypatch):
    monkeypatch.setenv("ATENDIMENTO_SLACK", "0")  # o .env local não religa o Slack
    cliente = _cliente(
        tmp_path, monkeypatch, ATENDIMENTO_LLM="1", ANTHROPIC_API_KEY="chave-de-teste"
    )

    saude = cliente.get("/api/saude").json()

    assert saude["leitor"] == "claude"
    assert saude["leitor_modelo"]
    assert saude["leitor_falhas"] == 0


def test_saude_nunca_mostra_segredos(tmp_path, monkeypatch):
    monkeypatch.setenv("ATENDIMENTO_SLACK", "0")  # o .env local não religa o Slack
    cliente = _cliente(
        tmp_path, monkeypatch, ATENDIMENTO_LLM="1", ANTHROPIC_API_KEY="chave-de-teste"
    )

    corpo = json.dumps(cliente.get("/api/saude").json())

    assert "chave-de-teste" not in corpo


def test_P5_saude_mostra_o_slack_em_socket_mode(tmp_path, monkeypatch):
    # Na máquina local o Slack roda por WebSocket: sem gancho HTTP, mas está ligado e a tela
    # precisa dizer isso no canal do time.
    monkeypatch.delenv("VERCEL", raising=False)
    cliente = _cliente(
        tmp_path,
        monkeypatch,
        ATENDIMENTO_LLM="0",
        ATENDIMENTO_SLACK="1",
        ATENDIMENTO_SLACK_MODO="socket",
        SLACK_BOT_TOKEN="xoxb-teste",
        SLACK_APP_TOKEN="xapp-teste",
        SLACK_CANAL_ID="C123",
    )

    saude = cliente.get("/api/saude").json()

    assert saude["slack"] == {"modo": "socket", "falhas": 0}
