"""Um único Analista por processo: avisos do fluxo do caso e do router /api/analista somam no
mesmo contador (limite de 300/dia de ferramentas.csv contado em um só lugar)."""

import pytest
from fastapi.testclient import TestClient

from atendimento.analista import detectar_padroes


@pytest.mark.integracao
def test_HG_19_caso_e_router_usam_o_mesmo_analista(tmp_path, monkeypatch):
    from atendimento.api.app import agente_real, criar_app

    monkeypatch.setenv("ATENDIMENTO_DB", str(tmp_path / "atendimento.db"))
    agente = agente_real()
    with TestClient(criar_app(agente)) as cliente:
        analista = agente.obter_analista()
        assert analista is not None
        pelo_router = cliente.post("/api/analista/padroes/cobranca_em_dobro/tratar").json()
        avisos_router = len(pelo_router["notificacoes"])
        assert avisos_router > 0
        assert sum(analista._enviados.values()) == avisos_router  # o router usou o do agente
        padrao = next(p for p in detectar_padroes(agente.base) if p.tipo == "contato_repetido")
        pelo_caso = agente.analista(
            fator="contato_repetido", order_ids=(padrao.escopo[0],), conversation_ids=()
        )
        assert agente.obter_analista() is analista
        assert sum(analista._enviados.values()) == avisos_router + pelo_caso["notificacoes"]
