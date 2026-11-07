"""API FastAPI (contrato W4 ↔ W5 do SPEC.md), com W1 falso e W2/W3 reais."""

import json

import pytest
from fastapi.testclient import TestClient
from fixtures.agente.falsos import BaseFalsa, FerramentasFalsas, anexo, captura, pedido

from atendimento.agente.caso import Agente
from atendimento.api.app import criar_app


def _cliente():
    base = BaseFalsa()
    base.conversa("AT1", ["O pote chegou amassado e vazou."], order_id="GBH000002")
    base.com_pedido(pedido("GBH000002", valor=260.0))
    base.com_anexo(anexo("AT1", "GBH000002", captura=captura(31)))
    base.conversa(
        "AT2", ["Bom dia", "meu cpf é 123.456.789-12, cadê o rastreio?"], order_id="GBH000001"
    )
    base.com_pedido(pedido("GBH000001", valor=120.0))
    agente = Agente(base, FerramentasFalsas(base))
    return TestClient(criar_app(agente))


def test_HP_01_fila_com_prioridade_e_estado():
    fila = _cliente().get("/api/fila").json()
    assert {c["conversation_id"] for c in fila} == {"AT1", "AT2"}
    campos = {"conversation_id", "canal", "marca", "assunto", "order_id", "data_abertura"}
    assert campos | {"prioridade", "estado"} <= set(fila[0])
    assert [c["prioridade"] for c in fila] == [1, 2]
    assert all(c["estado"] == "aberta" for c in fila)


def test_HP_09_processar_fila_devolve_placar_e_nenhuma_fica_aberta():
    cliente = _cliente()
    placar = cliente.post("/api/fila/processar").json()
    assert set(placar) == {
        "resolvidas_sozinho",
        "aguardando_aprovacao",
        "aguardando_cliente",
        "suspeitas",
        "escaladas",
        "valor_executado_rs",
        "custo_evitado_rs",
        "replay",
    }
    assert all(c["estado"] != "aberta" for c in cliente.get("/api/fila").json())
    assert cliente.get("/api/placar").json() == placar


def test_processar_uma_e_detalhar():
    cliente = _cliente()
    caso = cliente.post("/api/conversas/AT1/processar").json()
    assert caso["conversa"]["estado"] == "aguardando_aprovacao"
    detalhe = cliente.get("/api/conversas/AT1").json()
    assert set(detalhe) >= {
        "conversa",
        "mensagens",
        "pedido",
        "anexos",
        "veredicto",
        "decisao",
        "acoes",
        "resposta_ao_cliente",
    }
    assert detalhe["decisao"]["resultado"] == "pedir_aprovacao"
    assert detalhe["pedido"]["order_id"] == "GBH000002"


def test_conversa_inexistente_404():
    assert _cliente().get("/api/conversas/NAOEXISTE").status_code == 404


def test_HG_11_api_mascara_cpf_nas_mensagens():
    cliente = _cliente()
    cliente.post("/api/conversas/AT2/processar")
    corpo = cliente.get("/api/conversas/AT2").text
    assert "123.456.789" not in corpo
    assert "***.***.***-12" in corpo


def test_HP_10_aprovar_pelo_canal_executa_a_acao():
    cliente = _cliente()
    cliente.post("/api/conversas/AT1/processar")
    canal = cliente.get("/api/canal").json()
    pedido_aprovacao = next(m for m in canal if m["tipo"] == "aprovacao")
    assert pedido_aprovacao["estado"] == "pendente"
    resposta = cliente.post(
        f"/api/aprovacoes/{pedido_aprovacao['aprovacao_id']}/aprovar",
        json={"supervisor_id": "supervisor_01", "comentario": "ok"},
    )
    assert resposta.status_code == 200
    acoes = cliente.get("/api/acoes").json()
    reenvio = next(a for a in acoes if a["acao"] == "reenviar_produto")
    assert reenvio["aprovado_por"] == "supervisor_01"
    canal = cliente.get("/api/canal").json()
    assert next(m for m in canal if m["tipo"] == "aprovacao")["estado"] == "aprovada"


def test_HG_03_aprovacao_por_nao_supervisor_e_recusada_com_403():
    cliente = _cliente()
    cliente.post("/api/conversas/AT1/processar")
    aprovacao_id = next(m for m in cliente.get("/api/canal").json() if m["tipo"] == "aprovacao")[
        "aprovacao_id"
    ]
    resposta = cliente.post(
        f"/api/aprovacoes/{aprovacao_id}/aprovar", json={"supervisor_id": "atendente_01"}
    )
    assert resposta.status_code == 403


def test_rejeitar_exige_justificativa_e_registra():
    cliente = _cliente()
    cliente.post("/api/conversas/AT1/processar")
    aprovacao_id = next(m for m in cliente.get("/api/canal").json() if m["tipo"] == "aprovacao")[
        "aprovacao_id"
    ]
    resposta = cliente.post(
        f"/api/aprovacoes/{aprovacao_id}/rejeitar",
        json={"supervisor_id": "supervisor_02", "justificativa": "foto insuficiente"},
    )
    assert resposta.status_code == 200
    assert any(a["acao"] == "rejeitar_acao" for a in cliente.get("/api/acoes").json())


def test_aprovacao_inexistente_404():
    resposta = _cliente().post("/api/aprovacoes/APR-X/aprovar", json={"supervisor_id": "s"})
    assert resposta.status_code == 404


def test_eventos_sse_entrega_acoes_e_canal():
    cliente = _cliente()
    cliente.post("/api/conversas/AT1/processar")
    with cliente.stream("GET", "/api/eventos?desde=0&limite=3") as resposta:
        assert resposta.headers["content-type"].startswith("text/event-stream")
        corpo = "".join(resposta.iter_text())
    eventos = [json.loads(linha[6:]) for linha in corpo.splitlines() if linha.startswith("data: ")]
    assert len(eventos) == 3
    assert all({"tipo", "payload"} <= set(e) for e in eventos)


def test_cors_liberado_para_a_interface():
    resposta = _cliente().get("/api/placar", headers={"Origin": "http://localhost:5173"})
    assert resposta.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_F3_rotas_de_replay():
    from fixtures.agente.falsos import ReplayFalso

    base = BaseFalsa()
    replay = ReplayFalso(base)
    replay.historica("AT104936", ["A capinha chegou quebrada."], "GCH1", "2026-08-06 15:53:56")
    base.com_pedido(pedido("GCH1", valor=89.9))
    base.com_anexo(anexo("AT104936", "GCH1", captura=captura(31)))
    cliente = TestClient(criar_app(Agente(base, FerramentasFalsas(base), replay=replay)))
    casos = cliente.get("/api/replay/casos").json()
    assert casos[0]["conversation_id"] == "AT104936"
    caso = cliente.post("/api/replay/AT104936/processar").json()
    assert caso["caso"]["replay"] is True
    assert cliente.get("/api/fila").json() == []
    assert cliente.post("/api/replay/NAOEXISTE/processar").status_code == 404


def test_HG_03_aprovar_duas_vezes_da_conflito_e_nao_500():
    cliente = _cliente()
    cliente.post("/api/conversas/AT1/processar")
    aprovacao_id = next(m for m in cliente.get("/api/canal").json() if m["tipo"] == "aprovacao")[
        "aprovacao_id"
    ]
    url = f"/api/aprovacoes/{aprovacao_id}/aprovar"
    assert cliente.post(url, json={"supervisor_id": "supervisor_01"}).status_code == 200
    assert cliente.post(url, json={"supervisor_id": "supervisor_02"}).status_code in (403, 409)


@pytest.mark.integracao
def test_HG_12_subida_recria_a_base_sem_acoes_antigas(tmp_path, monkeypatch):
    from atendimento.api.app import agente_real

    db = tmp_path / "atendimento.db"
    monkeypatch.setenv("ATENDIMENTO_DB", str(db))
    primeiro = agente_real()
    primeiro.processar_fila()
    assert primeiro.acoes()
    segundo = agente_real()  # simula o --reload
    assert segundo.acoes() == []
    assert all(c["estado"] == "aberta" for c in segundo.fila())
