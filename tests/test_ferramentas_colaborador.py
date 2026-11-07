"""responder_colaborador no executor (HG-10): a resposta a um colaborador fica no log."""

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


def _resposta(papel=Papel.ATENDENTE, texto="Pedido de colaborador não muda a política."):
    return AcaoProposta(
        ferramenta="responder_colaborador", papel=papel, executado_por="agente", motivo=texto
    )


@pytest.mark.parametrize("papel", [Papel.ATENDENTE, Papel.ANALISTA, Papel.SUPERVISOR])
def test_HG_10_responder_colaborador_grava_em_acoes_agente(ferramentas, papel):
    registro = ferramentas.executar(_resposta(papel))
    assert registro.acao == "responder_colaborador"
    assert registro.sistema == "Canal do time"
    assert registro in ferramentas.acoes_registradas()


def test_HG_11_resposta_ao_colaborador_e_mascarada(ferramentas):
    ferramentas.executar(_resposta(texto="CPF 123.456.789-01 do cliente"))
    (texto,) = ferramentas.base.conexao.execute(
        "SELECT texto FROM mensagens_enviadas ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    assert "123.456.789-01" not in texto


def test_HG_10_catalogo_continua_valendo_para_o_papel(ferramentas):
    ferramentas._catalogo["responder_colaborador"]["papeis_permitidos"] = "supervisor"
    with pytest.raises(FerramentaNaoPermitida):
        ferramentas.executar(_resposta(Papel.ATENDENTE))
