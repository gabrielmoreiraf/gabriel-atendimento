"""Itens do revisor no executor: HG-02/HG-04 (decidir_suspeita), cancelar_pedido e
alterar_endereco só antes da separação (`ferramentas.csv`, somente_antes_da_separacao)."""

from pathlib import Path

import pytest

from atendimento.contratos import AcaoProposta, Papel
from atendimento.dados.carga import carregar
from atendimento.dados.repositorio import Base
from atendimento.ferramentas import FerramentaNaoPermitida, Ferramentas

FIXTURES = Path(__file__).parent / "fixtures" / "dados"


@pytest.fixture
def base(tmp_path):
    caminho = tmp_path / "base.db"
    carregar(FIXTURES, caminho)
    return Base(caminho)


@pytest.fixture
def ferramentas(base):
    return Ferramentas(base)


def _contar(base, tabela, where="1=1", *parametros):
    return base.conexao.execute(
        f"SELECT COUNT(*) FROM {tabela} WHERE {where}", parametros
    ).fetchone()[0]


def _sinalizar(ferramentas, executado_por="agente", papel=Papel.ATENDENTE):
    return ferramentas.executar(
        AcaoProposta(
            ferramenta="sinalizar_suspeita",
            papel=papel,
            executado_por=executado_por,
            conversation_id="AT116160",
            order_id="GBH473217",
            motivo="IMG000010 tem o mesmo hash de outro pedido",
        )
    )


def _decidir(executado_por="supervisor_02", decisao="improcedente"):
    return AcaoProposta(
        ferramenta="decidir_suspeita",
        papel=Papel.SUPERVISOR,
        executado_por=executado_por,
        conversation_id="AT116160",
        order_id="GBH473217",
        motivo=f"{decisao}: hash idêntico ao do pedido GCH533082",
    )


# ---------- HG-02 / HG-04: decidir_suspeita ----------


def test_HG_04_supervisor_decide_suspeita_e_registra(ferramentas, base):
    sinalizada = _sinalizar(ferramentas)

    registro = ferramentas.executar(_decidir(), decisao="improcedente")

    assert registro.acao == "decidir_suspeita"
    assert registro.executado_por == "supervisor_02"
    assert registro.referencia_sistema == sinalizada.referencia_sistema
    assert (
        _contar(
            base,
            "suspeitas",
            "suspeita_id = ? AND estado = 'improcedente'",
            sinalizada.referencia_sistema,
        )
        == 1
    )


def test_HG_04_quem_sinalizou_nao_decide(ferramentas, base):
    _sinalizar(ferramentas, executado_por="supervisor_02", papel=Papel.ATENDENTE)

    with pytest.raises(FerramentaNaoPermitida):
        ferramentas.executar(_decidir(executado_por="supervisor_02"), decisao="procedente")

    assert _contar(base, "suspeitas", "estado = 'pendente'") == 1
    assert _contar(base, "tentativas_bloqueadas", "ferramenta = 'decidir_suspeita'") == 1


def test_HG_04_decisao_invalida(ferramentas):
    _sinalizar(ferramentas)

    with pytest.raises(ValueError):
        ferramentas.executar(_decidir(), decisao="talvez")


def test_HG_02_papel_checado_antes_de_executavel(ferramentas, base):
    # alterar_endereco por supervisor: papel errado precisa bloquear e gravar a tentativa
    acao = AcaoProposta(
        ferramenta="alterar_endereco",
        papel=Papel.SUPERVISOR,
        executado_por="supervisor_01",
        order_id="GBH473217",
        motivo="Rua Nova, 10",
    )

    with pytest.raises(FerramentaNaoPermitida):
        ferramentas.executar(acao)

    assert _contar(base, "tentativas_bloqueadas", "ferramenta = 'alterar_endereco'") == 1


# ---------- cancelar_pedido / alterar_endereco: só antes da separação ----------


def _nao_separado(base, order_id="GBH476745"):
    with base.conexao:
        base.conexao.execute(
            "UPDATE pedidos SET data_separacao = '' WHERE order_id = ?", (order_id,)
        )
    return order_id


@pytest.mark.parametrize("ferramenta", ["cancelar_pedido", "alterar_endereco"])
def test_EC_somente_antes_da_separacao_recusa_pedido_separado(ferramentas, base, ferramenta):
    acao = AcaoProposta(
        ferramenta=ferramenta,
        papel=Papel.ATENDENTE,
        executado_por="agente",
        conversation_id="AT116160",
        order_id="GBH473217",  # separado em 2026-10-23
        motivo="pedido do cliente",
    )

    with pytest.raises(ValueError, match="separa"):
        ferramentas.executar(acao)

    assert _contar(base, "acoes_agente") == 0


def test_EC_cancelar_pedido_nao_separado_estorna_integral(ferramentas, base):
    order_id = _nao_separado(base)

    registro = ferramentas.executar(
        AcaoProposta(
            ferramenta="cancelar_pedido",
            papel=Papel.ATENDENTE,
            executado_por="agente",
            conversation_id="AT116473",
            order_id=order_id,
            motivo="arrependimento antes da separação",
        )
    )

    assert registro.acao == "cancelar_pedido"
    assert registro.valor_rs == pytest.approx(58.81)  # valor do pedido (fixture)
    assert (
        _contar(base, "estornos", "order_id = ? AND tipo = 'total' AND valor = '58.81'", order_id)
        == 1
    )


def test_EC_alterar_endereco_nao_separado_registra_sem_dado_pessoal(ferramentas, base):
    order_id = _nao_separado(base)

    registro = ferramentas.executar(
        AcaoProposta(
            ferramenta="alterar_endereco",
            papel=Papel.ATENDENTE,
            executado_por="agente",
            conversation_id="AT116473",
            order_id=order_id,
            motivo="Rua das Flores, 100. Contato (85) 98765-4321",
        )
    )

    assert registro.acao == "alterar_endereco"
    texto = base.conexao.execute(
        "SELECT texto FROM mensagens_enviadas WHERE mensagem_id = ?",
        (registro.referencia_sistema,),
    ).fetchone()[0]
    assert "98765" not in texto
