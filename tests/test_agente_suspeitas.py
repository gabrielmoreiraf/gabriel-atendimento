"""Item 7 do revisor: suspeita pendente suspende dinheiro no pedido (HG-07) e o supervisor
decide (HG-04, HG-08): procedente libera a política; improcedente encerra sem acusação."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from fixtures.agente.falsos import BaseFalsa, FerramentasFalsas, anexo, captura, pedido

from atendimento.agente.aprovacoes import AprovacaoRecusada
from atendimento.agente.caso import Agente
from atendimento.api.app import criar_app
from atendimento.contratos import AGORA

PALAVRAS = ("fraude", "golpe", "falso", "falsa", "mentira", "suspeit")


def _com_suspeita(valor=150.0):
    base = BaseFalsa()
    base.conversa("AT1", ["O pote chegou amassado e vazou."], order_id="GBH3")
    base.com_pedido(pedido("GBH3", valor=valor))
    base.com_anexo(anexo("AT1", "GBH3", "IMG1", hash_="hrep", captura=captura(31)))
    base.com_anexo(anexo("AT9", "GBH999999", "IMG9", hash_="hrep", captura=captura(10)))
    ferramentas = FerramentasFalsas(base)
    agente = Agente(base, ferramentas)
    caso = agente.processar("AT1")
    assert caso.estado == "suspeita"
    return base, ferramentas, agente, next(iter(agente.suspeitas))


def test_HG_07_suspeita_pendente_bloqueia_dinheiro_em_outra_conversa_do_mesmo_pedido():
    base, ferramentas, agente, _ = _com_suspeita()
    base.conversa("AT2", ["Paguei o boleto e cobraram no cartão também."], order_id="GBH3")
    ferramentas.pagamentos["GBH3"] = [
        {"transacao_id": "T1", "valor": "50.00", "status": "paga", "valor_estornado": "0.00"},
        {"transacao_id": "T2", "valor": "50.00", "status": "capturada", "valor_estornado": "0"},
    ]
    caso = agente.processar("AT2")
    assert not {"reembolsar", "solicitar_aprovacao"} & {r.acao for r in caso.acoes}
    assert caso.estado == "suspeita"
    assert "análise" in caso.resposta_ao_cliente


def test_suspeitas_pendentes_tem_prazo_de_politicas():
    _, _, agente, suspeita_id = _com_suspeita()
    pendentes = agente.suspeitas_pendentes()
    assert [s["suspeita_id"] for s in pendentes] == [suspeita_id]
    assert pendentes[0]["prazo"] == AGORA + timedelta(hours=24)
    mensagem = next(m for m in agente.canal if m["tipo"] == "suspeita")
    assert mensagem["suspeita_id"] == suspeita_id
    assert mensagem["prazo"] == (AGORA + timedelta(hours=24)).isoformat()
    assert "03/11/2026 08:00" in mensagem["texto"]


def test_HG_04_quem_sinalizou_nao_decide():
    _, _, agente, suspeita_id = _com_suspeita()
    with pytest.raises((AprovacaoRecusada, PermissionError)):
        agente.decidir_suspeita(suspeita_id, "agente", "procedente", "ok")


def test_HG_08_so_supervisor_decide():
    _, _, agente, suspeita_id = _com_suspeita()
    with pytest.raises(AprovacaoRecusada):
        agente.decidir_suspeita(suspeita_id, "atendente_01", "procedente", "ok")


def test_procedente_libera_a_acao_da_politica():
    _, _, agente, suspeita_id = _com_suspeita(valor=150.0)
    caso = agente.decidir_suspeita(suspeita_id, "supervisor_01", "procedente", "foto ok")
    assert "decidir_suspeita" in [r.acao for r in caso.acoes]
    assert "reenviar_produto" in [r.acao for r in caso.acoes]
    assert caso.estado == "resolvida"
    assert agente.suspeitas_pendentes() == []


def test_procedente_acima_da_alcada_pede_aprovacao():
    _, _, agente, suspeita_id = _com_suspeita(valor=260.0)
    caso = agente.decidir_suspeita(suspeita_id, "supervisor_01", "procedente", "foto ok")
    assert "reenviar_produto" not in [r.acao for r in caso.acoes]
    assert caso.estado == "aguardando_aprovacao"


def test_HG_07_improcedente_encerra_com_resposta_neutra():
    _, _, agente, suspeita_id = _com_suspeita()
    caso = agente.decidir_suspeita(suspeita_id, "supervisor_02", "improcedente", "hash repetido")
    assert "reenviar_produto" not in [r.acao for r in caso.acoes]
    assert caso.acoes[-1].acao == "encerrar_conversa"
    assert caso.estado == "resolvida"
    resposta = caso.resposta_ao_cliente.lower()
    assert resposta and not any(p in resposta for p in PALAVRAS)


def test_decidir_duas_vezes_e_recusado():
    _, _, agente, suspeita_id = _com_suspeita()
    agente.decidir_suspeita(suspeita_id, "supervisor_02", "improcedente", "x")
    with pytest.raises(AprovacaoRecusada):
        agente.decidir_suspeita(suspeita_id, "supervisor_01", "procedente", "y")


def test_rotas_de_suspeita():
    _, _, agente, suspeita_id = _com_suspeita()
    cliente = TestClient(criar_app(agente))
    pendentes = cliente.get("/api/suspeitas").json()
    assert pendentes[0]["suspeita_id"] == suspeita_id
    assert pendentes[0]["prazo"].startswith("2026-11-03T08:00")
    url = f"/api/suspeitas/{suspeita_id}/decidir"
    corpo = {"supervisor_id": "agente", "decisao": "procedente", "justificativa": "x"}
    assert cliente.post(url, json=corpo).status_code == 403
    corpo = {"supervisor_id": "supervisor_01", "decisao": "talvez", "justificativa": "x"}
    assert cliente.post(url, json=corpo).status_code == 422
    corpo = {"supervisor_id": "supervisor_01", "decisao": "procedente", "justificativa": "ok"}
    resposta = cliente.post(url, json=corpo)
    assert resposta.status_code == 200
    assert resposta.json()["conversa"]["estado"] == "resolvida"
    assert cliente.get("/api/suspeitas").json() == []
    assert cliente.post("/api/suspeitas/SUS-X/decidir", json=corpo).status_code == 404


def test_EC_20_elogio_secundario_de_reclamacao_e_ironia_e_nao_escala(monkeypatch):
    from dataclasses import replace

    import atendimento.agente.caso as caso_mod

    original = caso_mod.ler

    def ler_com_elogio(texto, **kw):
        return replace(original(texto, **kw), categoria_secundaria="elogio")

    monkeypatch.setattr(caso_mod, "ler", ler_com_elogio)
    base = BaseFalsa()
    base.conversa("AT1", ["Amei receber metade do pedido, faltou o brinde 🙃"], order_id="GBH1")
    base.com_pedido(pedido("GBH1", valor=80.0))
    caso = Agente(base, FerramentasFalsas(base)).processar("AT1")
    assert caso.categoria == "item_faltante"
    assert "acionar_pessoa" not in [r.acao for r in caso.acoes]
    assert caso.estado == "aguardando_cliente"
