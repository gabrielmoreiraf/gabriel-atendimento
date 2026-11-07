"""responder_duvida e validar_cupom (ferramentas.csv; politicas.csv: categorias.duvida_produto,
categorias.cupom_promocao.acoes_permitidas = validar_cupom). Executor real, base de fixture.

Fixtures: `tests/fixtures/dados` + `tests/fixtures/ferramentas_extra` (recorte de produtos.csv e
cupons.csv; uso_cupons.csv sintético sobre os pedidos da fixture).
"""

import shutil
from pathlib import Path

import pytest

from atendimento.contratos import Papel
from atendimento.dados.carga import carregar
from atendimento.dados.repositorio import Base
from atendimento.ferramentas import FerramentaNaoPermitida, Ferramentas

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def base(tmp_path):
    origem = tmp_path / "docs"
    shutil.copytree(FIXTURES / "dados", origem)
    for arquivo in (FIXTURES / "ferramentas_extra").glob("*.csv"):
        shutil.copy(arquivo, origem / arquivo.name)
    caminho = tmp_path / "base.db"
    carregar(origem, caminho)
    return Base(caminho)


@pytest.fixture
def ferramentas(base):
    return Ferramentas(base)


def _contar(base, tabela, where="1=1", *parametros):
    return base.conexao.execute(
        f"SELECT COUNT(*) FROM {tabela} WHERE {where}", parametros
    ).fetchone()[0]


# ---------- responder_duvida ----------


def test_EC_20_responder_duvida_usa_a_ficha_do_produto(ferramentas, base):
    resultado = ferramentas.responder_duvida("AT116597", sku="GOC-5046")

    assert resultado["precisa_pessoa"] is False
    assert resultado["sku"] == "GOC-5046"
    texto = resultado["resposta"]
    assert "Garrafa Fresh 650ml" in texto
    assert "Aço inox 304 com parede dupla a vácuo" in texto  # composicao
    assert "Mantém gelado por até 12 horas" in texto  # modo_de_uso
    enviada = base.conexao.execute(
        "SELECT destino, texto FROM mensagens_enviadas WHERE conversation_id = 'AT116597'"
    ).fetchall()
    assert [(e[0], e[1]) for e in enviada] == [("cliente", texto)]
    assert _contar(base, "acoes_agente", "acao = 'responder_duvida'") == 1


def test_EC_20_responder_duvida_inclui_advertencias(ferramentas):
    texto = ferramentas.responder_duvida("AT116673", sku="KSH-5001")["resposta"]

    assert "Advertências" in texto
    assert "Evite contato com os olhos" in texto


def test_EC_20_responder_duvida_nao_inventa_campo_vazio(ferramentas):
    # GOC-5046 não tem advertências na ficha: a resposta não cita advertências
    assert "Advertências" not in ferramentas.responder_duvida("AT1", sku="GOC-5046")["resposta"]


@pytest.mark.parametrize("sku", [None, "", "XXX-0000"])
def test_EC_20_sem_sku_ou_sem_ficha_precisa_de_pessoa(ferramentas, base, sku):
    resultado = ferramentas.responder_duvida("AT116657", sku=sku)

    assert resultado["precisa_pessoa"] is True
    assert resultado["resposta"] is None
    assert resultado["motivo"]
    assert _contar(base, "mensagens_enviadas") == 0


def test_HG_02_responder_duvida_so_atendente(ferramentas, base):
    with pytest.raises(FerramentaNaoPermitida):
        ferramentas.responder_duvida(
            "AT116597", sku="GOC-5046", papel=Papel.SUPERVISOR, executado_por="supervisor_01"
        )
    assert _contar(base, "tentativas_bloqueadas", "ferramenta = 'responder_duvida'") == 1


# ---------- validar_cupom ----------


def test_EC_20_cupom_inexistente(ferramentas):
    resultado = ferramentas.validar_cupom("NAOEXISTE")

    assert resultado["valido"] is False
    assert resultado["motivo"] == "cupom_inexistente"


def test_EC_20_cupom_valido_no_agora(ferramentas, base):
    resultado = ferramentas.validar_cupom("BEMVINDA10", conversation_id="AT116597")

    assert resultado["valido"] is True
    assert resultado["motivo"] is None
    assert _contar(base, "acoes_agente", "acao = 'validar_cupom'") == 1


def test_EC_20_cupom_expirado_no_agora(ferramentas):
    # OUTUBRO10: vigência 01/10 a 31/10/2026; agora = 02/11/2026
    resultado = ferramentas.validar_cupom("OUTUBRO10")

    assert resultado["valido"] is False
    assert resultado["motivo"] == "fora_da_vigencia"
    assert "31/10/2026" in resultado["detalhe"]


def test_EC_20_com_pedido_vale_a_data_do_pedido_e_o_valor_minimo(ferramentas):
    # GBH473217 de 22/10 (dentro da vigência), valor dos produtos R$ 89,90 < R$ 150
    resultado = ferramentas.validar_cupom("OUTUBRO10", order_id="GBH473217")

    assert resultado["valido"] is False
    assert resultado["motivo"] == "valor_minimo_nao_atingido"


def test_EC_20_cupom_de_outra_marca(ferramentas):
    # KOKESHI15 só vale para Kokeshi; GCH525121 é Gocase
    resultado = ferramentas.validar_cupom("KOKESHI15", order_id="GCH525121")

    assert resultado["valido"] is False
    assert resultado["motivo"] == "marca_nao_valida"


def test_EC_20_primeira_compra(ferramentas, base):
    assert ferramentas.validar_cupom("BEMVINDA10", order_id="GBH473217")["valido"] is True

    with base.conexao:  # o mesmo cliente já tinha comprado antes
        base.conexao.execute(
            "INSERT INTO pedidos (order_id, customer_id, marca, data_pedido, valor_produtos) "
            "VALUES ('GBH000001', 'CH761018', 'Kokeshi', '2026-01-10', '50.00')"
        )
    resultado = ferramentas.validar_cupom("BEMVINDA10", order_id="GBH473217")
    assert resultado["valido"] is False
    assert resultado["motivo"] == "exclusivo_primeira_compra"


def test_EC_20_limite_de_uso_por_cliente(ferramentas):
    # INFLU10: 2 por cliente; CH620178 já usou em 2 outros pedidos (uso_cupons da fixture)
    resultado = ferramentas.validar_cupom("INFLU10", order_id="GBH476745")

    assert resultado["valido"] is False
    assert resultado["motivo"] == "limite_por_cliente_atingido"


def test_EC_20_recusa_registrada_pela_plataforma(ferramentas):
    resultado = ferramentas.validar_cupom("KOKESHI15", order_id="GBH481046")

    assert resultado["valido"] is False
    assert resultado["motivo"] == "nao_acumula_com_outra_promocao"
    assert resultado["referencia"] == "USO900002"


def test_EC_20_uso_no_proprio_pedido_nao_conta_contra_o_limite(ferramentas):
    resultado = ferramentas.validar_cupom("INFLU10", order_id="GBH366247")

    assert resultado["valido"] is True
    assert resultado["referencia"] == "USO900001"


def test_HG_02_validar_cupom_so_atendente(ferramentas):
    with pytest.raises(FerramentaNaoPermitida):
        ferramentas.validar_cupom("BEMVINDA10", papel=Papel.ANALISTA, executado_por="analista_01")
