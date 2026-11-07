"""HG-11: `Base.mensagens` não devolve o nome completo do cliente da conversa."""

from pathlib import Path

import pytest

from atendimento.dados.carga import carregar
from atendimento.dados.repositorio import Base

FIXTURES = Path(__file__).parent / "fixtures" / "dados"


@pytest.fixture
def base(tmp_path):
    caminho = tmp_path / "base.db"
    carregar(FIXTURES, caminho)
    base = Base(caminho)
    with (
        base.conexao
    ):  # fixture: o cliente de AT116160 (CH761018) se chama "Cliente Teste"; nome inventado
        base.conexao.execute(
            "UPDATE clientes SET nome = 'Zuleica Tavendraz' WHERE customer_id = 'CH761018'"
        )
        base.conexao.execute(
            "INSERT INTO historico_mensagens (conversation_id, message_id, autor, timestamp, texto) "
            "VALUES ('AT116160', 'MS9999999', 'cliente', '2026-11-01 23:59:00', "
            "'Atenciosamente, ZULEICA TAVENDRAZ. CPF 123.456.789-09')"
        )
    return base


def test_HG_11_mensagens_mascaram_o_nome_do_cliente_da_conversa(base):
    textos = [m["texto"] for m in base.mensagens("AT116160")]

    assert "Atenciosamente, Zuleica T.. CPF ***.***.***-09" in textos
    assert not any("tavendraz" in t.lower() for t in textos)


def test_HG_11_mensagens_de_outra_conversa_nao_mudam(base):
    textos = [m["texto"] for m in base.mensagens("AT116171")]

    assert textos  # a conversa existe na fixture
    assert all("Zuleica T." not in t for t in textos)


def test_HG_11_conversa_sem_cliente_conhecido_continua_funcionando(base):
    assert base.mensagens("AT000000") == []
