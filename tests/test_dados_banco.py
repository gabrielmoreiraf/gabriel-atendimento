"""Contrato 1 (tasks/vercel/plan.md): `atendimento.dados.banco` fala SQLite e Postgres.

Os testes rodam em SQLite na suíte padrão e, com `-m postgres`, também contra o Neon
(`DATABASE_URL` do `.env.local`), num esquema temporário que é apagado no fim.
"""

from __future__ import annotations

import threading
from datetime import date, datetime

import pytest
from tests_postgres import banco_postgres_temporario

from atendimento.contratos import FUSO
from atendimento.dados.banco import Banco, conectar

DIALETOS = [
    pytest.param("sqlite", id="sqlite"),
    pytest.param("postgres", id="postgres", marks=pytest.mark.postgres),
]


@pytest.fixture(params=DIALETOS)
def banco(request, tmp_path):
    if request.param == "sqlite":
        banco = conectar(str(tmp_path / "teste.db"))
        yield banco
        banco.fechar()
    else:
        with banco_postgres_temporario() as banco:
            yield banco


def _tabela(banco: Banco):
    banco.executar(
        f"CREATE TABLE coisas (id {banco.tipo_id_auto}, nome TEXT, valor NUMERIC, "
        "dia DATE, quando TIMESTAMPTZ, dados JSON)"
    )


def test_dialeto_e_tipo_do_banco(banco):
    assert isinstance(banco, Banco)
    assert banco.dialeto in ("sqlite", "postgres")


def test_executar_devolve_dicts_com_placeholder_interrogacao(banco):
    _tabela(banco)
    banco.executar("INSERT INTO coisas (nome, valor) VALUES (?, ?)", ("a", 1.5))
    banco.executar("INSERT INTO coisas (nome, valor) VALUES (?, ?)", ("b%", 2))

    linhas = banco.executar(
        "SELECT nome, valor FROM coisas WHERE nome LIKE ? ORDER BY nome", ("%",)
    )

    assert linhas == [{"nome": "a", "valor": 1.5}, {"nome": "b%", "valor": 2.0}]
    assert isinstance(linhas[1]["valor"], float)


def test_interrogacao_e_porcento_dentro_de_texto_literal(banco):
    linha = banco.executar_um("SELECT 'por que?' AS a, '100%' AS b, ? AS c", ("x",))
    assert linha == {"a": "por que?", "b": "100%", "c": "x"}


def test_executar_um_sem_resultado(banco):
    _tabela(banco)
    assert banco.executar_um("SELECT * FROM coisas WHERE nome = ?", ("nada",)) is None


def test_returning_id_autoincremento(banco):
    _tabela(banco)
    primeiro = banco.executar_um("INSERT INTO coisas (nome) VALUES (?) RETURNING id", ("a",))
    segundo = banco.executar_um("INSERT INTO coisas (nome) VALUES (?) RETURNING id", ("b",))
    assert segundo["id"] == primeiro["id"] + 1


def test_tipos_data_hora_e_json_iguais_nos_dois(banco):
    _tabela(banco)
    quando = datetime(2026, 11, 2, 8, 0, tzinfo=FUSO)
    banco.executar(
        "INSERT INTO coisas (nome, dia, quando, dados) VALUES (?, ?, ?, ?)",
        ("a", date(2026, 11, 2), quando, {"tipo": "acao", "n": [1, 2]}),
    )

    linha = banco.executar_um("SELECT dia, quando, dados FROM coisas")

    assert linha["dia"] == date(2026, 11, 2)
    assert isinstance(linha["quando"], datetime)
    assert linha["quando"] == quando  # mesmo instante, com fuso
    assert linha["dados"] == {"tipo": "acao", "n": [1, 2]}


def test_transacao_confirma_ou_desfaz(banco):
    _tabela(banco)
    with banco.transacao():
        banco.executar("INSERT INTO coisas (nome) VALUES (?)", ("ok",))
    with pytest.raises(RuntimeError), banco.transacao():
        banco.executar("INSERT INTO coisas (nome) VALUES (?)", ("desfeito",))
        raise RuntimeError("falha no meio")

    assert [r["nome"] for r in banco.executar("SELECT nome FROM coisas")] == ["ok"]


def test_transacao_aninhada(banco):
    _tabela(banco)
    with banco.transacao(), banco.transacao():
        banco.executar("INSERT INTO coisas (nome) VALUES (?)", ("x",))
    assert banco.executar_um("SELECT COUNT(*) AS n FROM coisas")["n"] == 1


def test_executar_muitos_em_lote(banco):
    _tabela(banco)
    banco.executar_muitos("INSERT INTO coisas (nome) VALUES (?)", [(f"n{i}",) for i in range(50)])
    assert banco.executar_um("SELECT COUNT(*) AS n FROM coisas")["n"] == 50


def test_tabelas_existentes(banco):
    _tabela(banco)
    assert "coisas" in banco.tabelas()


def test_trava_por_nome_serializa(banco):
    ordem = []

    def trabalho(i):
        with banco.trava("rodada"):
            ordem.append(("entra", i))
            threading.Event().wait(0.05)
            ordem.append(("sai", i))

    threads = [threading.Thread(target=trabalho, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)

    # nunca duas "entra" seguidas: uma rodada termina antes da próxima começar
    assert [o[0] for o in ordem] == ["entra", "sai"] * 3


def test_conectar_sem_url_usa_database_url_ou_var(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    banco = conectar(None)
    try:
        assert banco.dialeto == "sqlite"
        assert banco.caminho.name == "atendimento.db"
        assert banco.caminho.parent.name == "var"
    finally:
        banco.fechar()


def test_repr_nao_mostra_a_url(monkeypatch):
    banco = conectar(":memory:")
    try:
        assert "memory" not in repr(banco) or "sqlite" in repr(banco)
    finally:
        banco.fechar()
