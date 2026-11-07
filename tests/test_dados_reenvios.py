"""EC-19 / Q15: reenvios anteriores do cliente = só `tipo == "reenvio"` do histórico do OMS."""

from pathlib import Path

import pytest

from atendimento.contratos import AcaoProposta, Papel
from atendimento.dados.carga import carregar
from atendimento.dados.repositorio import Base
from atendimento.ferramentas import Ferramentas

FIXTURES = Path(__file__).parent / "fixtures" / "dados"


@pytest.fixture
def base(tmp_path):
    caminho = tmp_path / "base.db"
    carregar(FIXTURES, caminho)
    return Base(caminho)


def test_EC_19_reenvios_contam_so_tipo_reenvio(base):
    # fixture: CH660017 tem 1 reenvio; CH502758 tem só uma nova_producao
    assert base.reenvios_do_cliente("CH660017") == 1
    assert base.reenvios_do_cliente("CH502758") == 0


def test_EC_19_reenvio_gravado_pelo_agente_nao_conta_como_historico(base):
    Ferramentas(base).executar(
        AcaoProposta(
            ferramenta="reenviar_produto",
            papel=Papel.ATENDENTE,
            executado_por="agente",
            conversation_id="AT999001",
            order_id="GBH366247",  # pedido do CH660017
            valor_rs=50.0,
            motivo="avaria",
        )
    )
    gravadas = base.conexao.execute(
        "SELECT COUNT(*) FROM trocas_reenvios WHERE customer_id = 'CH660017'"
    ).fetchone()[0]

    assert gravadas == 2  # o agente gravou a linha no OMS simulado
    assert base.reenvios_do_cliente("CH660017") == 1  # mas o histórico continua 1
