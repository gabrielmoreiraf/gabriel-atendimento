"""HP-10 e P5 no Vercel: com o Slack em modo HTTP, a API espelha o canal do time depois de
cada requisição que muda o estado e posta o resumo ao fim da rodada.

Também cobre a subida sem lifespan (o agente é criado na primeira requisição).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import atendimento.api.app as modulo
from atendimento.dados.carga import carregar

FIXTURES = Path(__file__).parent / "fixtures" / "dados"


class GanchoFalso:
    def __init__(self):
        self.mensagens = []
        self.rodadas = []

    def mensagem_gravada(self, mensagem):
        self.mensagens.append(mensagem)

    def rodada_terminada(self, placar):
        self.rodadas.append(placar)


def _ambiente(tmp_path, monkeypatch):
    pronta = tmp_path / "pronta.db"
    carregar(FIXTURES, pronta)
    monkeypatch.setenv("ATENDIMENTO_BASE_PRONTA", str(pronta))
    monkeypatch.setenv("ATENDIMENTO_DB", str(tmp_path / "atendimento.db"))
    monkeypatch.setenv("ATENDIMENTO_LLM", "0")


def test_P5_sem_lifespan_o_agente_nasce_na_primeira_requisicao(tmp_path, monkeypatch):
    _ambiente(tmp_path, monkeypatch)
    cliente = TestClient(modulo.criar_app())  # sem `with`: o lifespan não roda

    resposta = cliente.get("/api/fila")

    assert resposta.status_code == 200
    assert resposta.json()


@pytest.mark.integracao
def test_HP_10_processar_fila_espelha_o_canal_e_posta_o_resumo(tmp_path, monkeypatch):
    # a rodada inteira precisa da base real (docs/, somente leitura)
    monkeypatch.delenv("ATENDIMENTO_BASE_PRONTA", raising=False)
    monkeypatch.setenv("ATENDIMENTO_DB", str(tmp_path / "atendimento.db"))
    monkeypatch.setenv("ATENDIMENTO_LLM", "0")
    gancho = GanchoFalso()
    monkeypatch.setattr(modulo, "criar_gancho_slack", lambda agente: gancho)
    cliente = TestClient(modulo.criar_app())

    placar = cliente.post("/api/fila/processar").json()

    assert gancho.rodadas == [placar]
    assert gancho.mensagens, "as mensagens do canal devem ir ao gancho do Slack"


def test_HP_10_get_nao_dispara_o_espelho(tmp_path, monkeypatch):
    _ambiente(tmp_path, monkeypatch)
    gancho = GanchoFalso()
    monkeypatch.setattr(modulo, "criar_gancho_slack", lambda agente: gancho)
    cliente = TestClient(modulo.criar_app())

    cliente.get("/api/fila")

    assert gancho.mensagens == [] and gancho.rodadas == []
