"""abrir_incidente e notificar_clientes no executor (HG-17, HG-19). Fixtures do W1."""

from __future__ import annotations

from pathlib import Path

import pytest

from atendimento.contratos import AcaoProposta, Papel
from atendimento.dados.carga import carregar
from atendimento.dados.repositorio import Base
from atendimento.ferramentas import FerramentaNaoPermitida, Ferramentas

FIXTURES = Path(__file__).parent / "fixtures" / "dados"


@pytest.fixture
def ferramentas(tmp_path):
    caminho = tmp_path / "base.db"
    carregar(FIXTURES, caminho)
    return Ferramentas(Base(caminho))


def _acao(ferramenta, papel=Papel.ANALISTA, **kw):
    return AcaoProposta(ferramenta=ferramenta, papel=papel, executado_por="agente_analista", **kw)


def test_HG_17_abrir_incidente_registra_inc(ferramentas):
    registro = ferramentas.executar(
        _acao("abrir_incidente", motivo="cobrança em dobro: 12 pedidos")
    )
    assert registro.acao == "abrir_incidente"
    assert registro.referencia_sistema == "INC-000001"
    assert registro.sistema == "Gestão de incidentes"
    segundo = ferramentas.executar(_acao("abrir_incidente", motivo="outro"))
    assert segundo.referencia_sistema == "INC-000002"
    assert [r.acao for r in ferramentas.acoes_registradas()][-2:] == [
        "abrir_incidente",
        "abrir_incidente",
    ]


def test_HG_17_notificar_clientes_registra_aviso_por_pedido(ferramentas):
    registro = ferramentas.executar(
        _acao("notificar_clientes", order_id="P1", motivo="Aviso de cobrança duplicada.")
    )
    assert registro.acao == "notificar_clientes"
    assert registro.order_id == "P1"
    assert registro.referencia_sistema == "AVISO-000001"
    assert registro.sistema == "Central de atendimento"


def test_HG_19_atendente_nao_abre_incidente_nem_notifica(ferramentas):
    for nome in ("abrir_incidente", "notificar_clientes"):
        with pytest.raises(FerramentaNaoPermitida):
            ferramentas.executar(_acao(nome, papel=Papel.ATENDENTE, order_id="P1"))


def test_HG_17_notificar_respeita_maximo_por_dia_do_catalogo(ferramentas):
    ferramentas._catalogo["notificar_clientes"]["limites"] = '{"max_por_dia": 2}'
    for pedido in ("P1", "P2"):
        ferramentas.executar(_acao("notificar_clientes", order_id=pedido, motivo="aviso"))
    with pytest.raises(FerramentaNaoPermitida):
        ferramentas.executar(_acao("notificar_clientes", order_id="P3", motivo="aviso"))
