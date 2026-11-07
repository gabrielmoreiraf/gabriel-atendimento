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


# ---------- HG-11: nome completo do cliente (`nomes=`) ----------


def test_HG_11_nome_completo_vira_primeiro_nome_e_inicial():
    texto = "Atenciosamente, Zuleica Tavendraz"
    assert mascarar(texto, nomes=("Zuleica Tavendraz",)) == "Atenciosamente, Zuleica T."


@pytest.mark.parametrize(
    "escrito", ["ZULEICA TAVENDRAZ", "zuleica tavendraz", "Zuleica  Tavendraz"]
)
def test_HG_11_nome_com_variacao_de_caixa_e_espaco(escrito):
    assert mascarar(f"Att, {escrito}.", nomes=("Zuleica Tavendraz",)) == "Att, Zuleica T.."


def test_HG_11_nome_com_variacao_de_acento():
    assert mascarar("Att, Odilia Quarembe", nomes=("Odília Quarembe",)) == "Att, Odília Q."
    assert mascarar("Att, Odília Quarembe", nomes=("Odilia Quarembe",)) == "Att, Odilia Q."


def test_HG_11_nome_de_tres_partes_completo_e_primeiro_mais_ultimo():
    nome = ("Rosimeire Clarinda Vostrel",)
    assert mascarar("Obrigada, Rosimeire Clarinda Vostrel", nomes=nome) == "Obrigada, Rosimeire V."
    assert mascarar("Obrigada, Rosimeire Vostrel", nomes=nome) == "Obrigada, Rosimeire V."
    assert mascarar("Obrigada, Clarinda Vostrel", nomes=nome) == "Obrigada, Rosimeire V."


def test_HG_11_so_o_primeiro_nome_fica():
    nome = ("Rosimeire Clarinda Vostrel",)
    assert mascarar("Obrigada, Rosimeire Clarinda", nomes=nome) == "Obrigada, Rosimeire Clarinda"
    assert mascarar("Oi, sou a Zuleica", nomes=("Zuleica Tavendraz",)) == "Oi, sou a Zuleica"


def test_HG_11_nome_dentro_de_outra_palavra_nao_e_trocado():
    assert (
        mascarar("Zuleica Tavendrazinho", nomes=("Zuleica Tavendraz",)) == "Zuleica Tavendrazinho"
    )


def test_HG_11_nome_junto_com_outros_dados():
    texto = "Zuleica Tavendraz, CPF 123.456.789-09, ana@x.com"
    assert mascarar(texto, nomes=("Zuleica Tavendraz",)) == (
        "Zuleica T., CPF ***.***.***-09, a***@x.com"
    )


@pytest.mark.parametrize("nomes", [(), (None,), ("",), ("Zuleica",)])
def test_HG_11_sem_nome_completo_comportamento_de_hoje(nomes):
    texto = "Zuleica Tavendraz, tel (85) 98765-4321"
    assert (
        mascarar(texto, nomes=nomes) == mascarar(texto) == "Zuleica Tavendraz, tel (**) *****-4321"
    )


@pytest.mark.integracao
def test_HG_11_nenhum_nome_completo_de_cliente_sobra_nas_mensagens():
    clientes = {r["customer_id"]: r["nome"] for r in _csv("clientes.csv")}
    dono = {r["conversation_id"]: r["customer_id"] for r in _csv("historico_conversas.csv")}
    dono |= {r["conversation_id"]: r["customer_id"] for r in _csv("fila_aberta.csv")}
    antes, depois = set(), set()
    for linha in _csv("historico_mensagens.csv"):
        nome = clientes.get(dono.get(linha["conversation_id"], ""), "")
        if linha["autor"] != "cliente" or not nome:
            continue
        if _tem_nome_completo(linha["texto"], nome):
            antes.add(linha["conversation_id"])
        if _tem_nome_completo(mascarar(linha["texto"], nomes=(nome,)), nome):
            depois.add(linha["conversation_id"])

    assert len(antes) > 300  # a base tem o problema (revisor: 314 conversas)
    assert sorted(depois) == []


def _csv(nome):
    with open(DOCS / nome, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _sem_acento(texto):
    import unicodedata

    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


def _tem_nome_completo(texto, nome):
    """Primeiro nome + último sobrenome, ou o nome inteiro, como palavras (sem acento/caixa)."""
    partes = _sem_acento(nome).split()
    alvo = _sem_acento(texto)
    candidatos = {" ".join(partes), f"{partes[0]} {partes[-1]}"}
    return any(re.search(rf"(?<!\w){re.escape(c)}(?!\w)", alvo) for c in candidatos)
