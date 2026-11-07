"""HG-11 / AGENTS.md regra 6: CPF, cartão, telefone e e-mail nunca saem sem máscara."""

import csv
import re
from pathlib import Path

import pytest

from atendimento.privacidade import mascarar, mascarar_cpf, mascarar_email, mascarar_telefone

DOCS = Path(__file__).resolve().parents[1] / "docs"


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("meu cpf é 123.456.789-09", "meu cpf é ***.***.***-09"),
        ("cpf 12345678909 ok", "cpf ***.***.***-09 ok"),
    ],
)
def test_HG_11_cpf(texto, esperado):
    assert mascarar(texto) == esperado


@pytest.mark.parametrize(
    "cartao",
    ["4111 1111 1111 1234", "4111-1111-1111-1234", "4111111111111234", "4111.1111.1111.1234"],
)
def test_HG_11_cartao_mantem_so_os_4_finais(cartao):
    assert mascarar(f"cartão {cartao} foi cobrado") == "cartão **** **** **** 1234 foi cobrado"


@pytest.mark.parametrize(
    "telefone",
    ["(85) 98765-4321", "85 98765-4321", "+55 85 98765-4321", "(85) 3456-4321", "85 3456 4321"],
)
def test_HG_11_telefone_mantem_so_os_4_finais(telefone):
    assert mascarar(f"me liga no {telefone} por favor") == "me liga no (**) *****-4321 por favor"


def test_HG_11_onze_digitos_sem_pontuacao_viram_mascara_de_cpf():
    # CPF ou celular? Ambíguo: usa a máscara que expõe menos (2 dígitos, não 4).
    assert mascarar("contato 85987654321") == "contato ***.***.***-21"


def test_HG_11_email():
    assert mascarar("escreve para maria.silva+loja@exemplo.com.br hoje") == (
        "escreve para m***@exemplo.com.br hoje"
    )


def test_HG_11_texto_com_varios_dados():
    texto = "CPF 123.456.789-09, tel (11) 91234-5678, e-mail ana@x.com, cartão 5500 0000 0000 0004"
    saida = mascarar(texto)

    assert saida == (
        "CPF ***.***.***-09, tel (**) *****-5678, e-mail a***@x.com, cartão **** **** **** 0004"
    )


@pytest.mark.parametrize(
    "texto",
    [
        "Pedido GBH491723",
        "protocolo OMS000123 e TRX00005946",
        "rastreio VL59160032895",
        "entregue em 2026-11-02 08:00:00",
        "estorno de R$ 1.118,80",
        "chegou dia 27/10/2026",
    ],
)
def test_HG_11_nao_mascara_ids_datas_e_valores(texto):
    assert mascarar(texto) == texto


def test_HG_11_mascaras_de_campo():
    assert mascarar_cpf("123.456.789-09") == "***.***.***-09"
    assert mascarar_telefone("(85) 98765-4321") == "(**) *****-4321"
    assert mascarar_email("maria@exemplo.com") == "m***@exemplo.com"


def test_HG_11_texto_vazio():
    assert mascarar("") == ""


@pytest.mark.integracao
def test_HG_11_nenhuma_mensagem_da_base_sobra_com_dado_pessoal():
    sobra = re.compile(r"\d[\d .()-]{7,}\d|[\w.+-]+@[\w-]+\.\w+")
    with open(DOCS / "historico_mensagens.csv", encoding="utf-8", newline="") as f:
        for linha in csv.DictReader(f):
            saida = mascarar(linha["texto"])
            for achado in sobra.findall(saida):
                digitos = re.sub(r"\D", "", achado)
                assert "@" not in achado or "***@" in achado, linha["message_id"]
                assert "@" in achado or len(digitos) < 8, linha["message_id"]
