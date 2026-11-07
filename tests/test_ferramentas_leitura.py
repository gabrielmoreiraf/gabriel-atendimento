"""Ferramentas de leitura (Q17): rastreio e pagamento, com registro da consulta."""

from pathlib import Path

import pytest

from atendimento.dados.carga import carregar
from atendimento.dados.repositorio import Base
from atendimento.ferramentas import Ferramentas

FIXTURES = Path(__file__).parent / "fixtures" / "dados"


@pytest.fixture
def ferramentas(tmp_path):
    caminho = tmp_path / "base.db"
    carregar(FIXTURES, caminho)
    return Ferramentas(Base(caminho))


def test_HP_08_consultar_rastreio_em_ordem_e_registrado(ferramentas):
    eventos = ferramentas.consultar_rastreio("GBH473217", conversation_id="AT116160")

    assert eventos[-1]["status"] == "em_transferencia"
    assert eventos[-1]["portal"] == "Expressa Já"
    datas = [e["data_hora_evento"] for e in eventos]
    assert datas == sorted(datas)
    registro = ferramentas.acoes_registradas()[-1]
    assert (registro.acao, registro.sistema) == ("consultar_rastreio", "Portal Expressa Já")


def test_HP_08_verificar_pagamento_sem_cartao_completo(ferramentas):
    transacoes = ferramentas.verificar_pagamento("GBH473217")

    assert [t["transacao_id"] for t in transacoes] == ["TRX00005360"]
    assert transacoes[0]["status"] == "capturada"
    assert ferramentas.acoes_registradas()[-1].sistema == "Gateway de pagamentos"


def test_HP_08_leitura_de_pedido_sem_dados_devolve_lista_vazia(ferramentas):
    assert ferramentas.consultar_rastreio("NAOEXISTE") == []
    assert ferramentas.verificar_pagamento("NAOEXISTE") == []
