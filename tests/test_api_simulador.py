"""Simulador de WhatsApp: o cliente escreve, a mensagem entra na fila como uma conversa nova e o
Gabriel responde pelo mesmo fluxo (leitor, pedido por ID, política, ferramentas).

O canal real (WhatsApp Business) fica para integração futura; aqui ele é a tela da demo.
"""

import csv
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import atendimento.api.app as modulo

DOCS = Path(__file__).resolve().parents[1] / "docs"
pytestmark = pytest.mark.integracao
CLIENTE = "CH761018"
PEDIDO = "GBH473217"  # Kokeshi, em trânsito


def _cliente(tmp_path, monkeypatch):
    # o fluxo completo do agente precisa da base real (docs/, somente leitura)
    monkeypatch.delenv("ATENDIMENTO_BASE_PRONTA", raising=False)
    monkeypatch.setenv("ATENDIMENTO_DB", str(tmp_path / "atendimento.db"))
    monkeypatch.setenv("ATENDIMENTO_LLM", "0")
    monkeypatch.setenv("ATENDIMENTO_SLACK", "0")  # o .env local não religa o Slack
    return TestClient(modulo.criar_app())


def test_HP_simulador_lista_clientes_com_pedidos_e_nome_mascarado(tmp_path, monkeypatch):
    cliente = _cliente(tmp_path, monkeypatch)

    clientes = cliente.get("/api/simulador/clientes").json()

    assert clientes, "a demo precisa de clientes para escolher"
    with open(DOCS / "clientes.csv", encoding="utf-8") as arquivo:
        nomes = {c["customer_id"]: c["nome"] for c in csv.DictReader(arquivo)}
    for item in clientes:
        assert item["pedidos"], "todo cliente da demo tem pedido"
        completo = nomes[item["customer_id"]]
        assert item["nome"] != completo  # HG-11: nunca o nome completo
        assert item["nome"].split()[0] == completo.split()[0]  # "Primeiro S."


def test_HP_mensagem_do_cliente_entra_na_fila_e_o_gabriel_responde(tmp_path, monkeypatch):
    cliente = _cliente(tmp_path, monkeypatch)

    resposta = cliente.post(
        "/api/simulador/mensagem",
        json={"customer_id": CLIENTE, "order_id": PEDIDO, "texto": "Cadê meu pedido? Não chegou."},
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["conversation_id"].startswith("WPP-")
    assert corpo["resposta"], "o Gabriel precisa responder o cliente"
    fila = [c["conversation_id"] for c in cliente.get("/api/fila").json()]
    assert corpo["conversation_id"] in fila
    caso = cliente.get(f"/api/conversas/{corpo['conversation_id']}").json()
    assert caso["pedido"]["order_id"] == PEDIDO  # conhece o cliente pelo cadastro


def test_HP_segunda_mensagem_leva_a_conversa_anterior(tmp_path, monkeypatch):
    cliente = _cliente(tmp_path, monkeypatch)
    primeira = cliente.post(
        "/api/simulador/mensagem",
        json={"customer_id": CLIENTE, "order_id": PEDIDO, "texto": "Oi, tudo bem?"},
    ).json()

    segunda = cliente.post(
        "/api/simulador/mensagem",
        json={
            "customer_id": CLIENTE,
            "order_id": PEDIDO,
            "texto": "Quero saber do rastreio do meu pedido.",
            "anterior": primeira["conversation_id"],
        },
    ).json()

    assert segunda["conversation_id"] != primeira["conversation_id"]
    textos = [m["texto"] for m in segunda["mensagens"]]
    assert "Oi, tudo bem?" in textos
    assert "Quero saber do rastreio do meu pedido." in textos


def test_HG_simulador_cliente_desconhecido_da_404(tmp_path, monkeypatch):
    cliente = _cliente(tmp_path, monkeypatch)

    resposta = cliente.post(
        "/api/simulador/mensagem", json={"customer_id": "CH000000", "texto": "oi"}
    )

    assert resposta.status_code == 404
