"""Carga de docs/ (aqui, a fixture) no Postgres: idempotente, em lote, sem imprimir a URL.

Roda só com `-m postgres`, num esquema temporário do Neon (`tests_postgres`).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tests_postgres import banco_postgres_temporario, url_postgres

from atendimento.dados.banco import conectar
from atendimento.dados.carga import TABELAS_DO_AGENTE, carregar, main
from atendimento.dados.repositorio import Base
from atendimento.ferramentas import Ferramentas

FIXTURES = Path(__file__).parent / "fixtures" / "dados"

pytestmark = pytest.mark.postgres


def test_carga_no_postgres_cria_tabelas_com_as_contagens_dos_csv():
    with banco_postgres_temporario() as banco:
        contagens = carregar(FIXTURES, banco)

        assert contagens["pedidos"] == 5
        for tabela, n in contagens.items():
            assert banco.executar_um(f'SELECT COUNT(*) AS n FROM "{tabela}"')["n"] == n
        assert set(TABELAS_DO_AGENTE) <= banco.tabelas()


def test_carga_no_postgres_e_idempotente():
    with banco_postgres_temporario() as banco:
        primeira = carregar(FIXTURES, banco)
        segunda = carregar(FIXTURES, banco)

        assert primeira == segunda
        assert banco.executar_um("SELECT COUNT(*) AS n FROM pedidos")["n"] == primeira["pedidos"]


def test_base_e_ferramentas_funcionam_sobre_o_postgres():
    with banco_postgres_temporario() as banco:
        carregar(FIXTURES, banco)
        base = Base(banco)

        pedido = base.pedido("GBH366247")
        assert pedido is not None and pedido.customer_id == "CH660017"
        assert pedido.valor == pytest.approx(162.72)
        assert [c["conversation_id"] for c in base.fila()] == ["AT116160", "AT116171", "AT116473"]
        assert base.reenvios_do_cliente("CH660017") == 1

        from atendimento.contratos import AcaoProposta, Papel

        ferramentas = Ferramentas(base)
        acao = AcaoProposta(
            ferramenta="reenviar_produto",
            papel=Papel.ATENDENTE,
            executado_por="agente",
            conversation_id="AT116160",
            order_id="GBH473217",
            valor_rs=50.0,
            motivo="extravio",
        )
        primeiro = ferramentas.executar(acao)
        repetido = ferramentas.executar(acao)  # HG-12: idempotente também no Postgres
        assert repetido == primeiro
        assert [r.acao for r in ferramentas.acoes_registradas()] == ["reenviar_produto"]
        assert base.reenvios_do_cliente("CH761018") == 0  # linha do agente não conta


def test_cli_nao_imprime_a_url(capsys, monkeypatch):
    url = url_postgres()
    if not url:
        pytest.skip("sem DATABASE_URL")
    with banco_postgres_temporario() as banco:
        esquema = banco.esquema
        main(["--origem", str(FIXTURES), "--destino", url, "--esquema", esquema])
        saida = capsys.readouterr()

        assert url not in saida.out and url not in saida.err
        assert "postgres" in saida.out.lower()
        assert (
            conectar(url, esquema=esquema).executar_um("SELECT COUNT(*) AS n FROM pedidos")["n"]
            == 5
        )
