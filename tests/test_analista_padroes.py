"""Agente analista (P4, HG-17, HG-19, HG-23). Base mínima montada no próprio teste."""

from __future__ import annotations

import csv
import shutil
from datetime import datetime
from pathlib import Path

import pytest

from atendimento.analista import (
    Analista,
    Padrao,
    canal_com_consentimento,
    chamar_analista,
    detectar_padroes,
)
from atendimento.contratos import FUSO
from atendimento.dados.carga import carregar
from atendimento.dados.repositorio import Base
from atendimento.ferramentas import Ferramentas

FIXTURES_W1 = Path(__file__).parent / "fixtures" / "dados"

PAGAMENTOS = [
    # P1: duas capturas, nenhuma estornada -> cobrança em dobro aberta
    ("T1", "P1", "C1", "capturada"),
    ("T2", "P1", "C1", "capturada"),
    # P2: duas, uma estornada -> já resolvido
    ("T3", "P2", "C2", "paga"),
    ("T4", "P2", "C2", "estornada"),
    # P3: paga + capturada -> aberta
    ("T5", "P3", "C3", "paga"),
    ("T6", "P3", "C3", "capturada"),
    # P4: uma só
    ("T7", "P4", "C4", "capturada"),
    # P5: duas capturas, cliente sem consentimento em nenhum canal
    ("T8", "P5", "C5", "capturada"),
    ("T9", "P5", "C5", "capturada"),
]
CLIENTES = [
    # customer_id, canal_preferido, whatsapp, email
    ("C1", "whatsapp", "sim", "sim"),
    ("C2", "email", "sim", "sim"),
    ("C3", "whatsapp", "não", "sim"),  # prefere WhatsApp, mas só consentiu e-mail
    ("C4", "email", "sim", "não"),
    ("C5", "whatsapp", "não", "não"),
]
CONVERSAS = [
    # conversation_id, customer_id, order_id
    ("AT1", "C1", "P1"),
    ("AT2", "C1", "P1"),
    ("AT3", "C2", "P2"),
    ("AT4", "C4", "P4"),
    ("AT5", "C4", "P4"),
    ("AT6", "C4", "P4"),
    ("AT7", "C3", ""),
]


def _escrever(pasta: Path, nome: str, cabecalho: list[str], linhas: list[tuple]) -> None:
    with open(pasta / f"{nome}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cabecalho)
        w.writerows(linhas)


@pytest.fixture
def base(tmp_path):
    origem = tmp_path / "csv"
    shutil.copytree(FIXTURES_W1, origem)
    _escrever(
        origem,
        "pagamentos_gateway",
        ["transacao_id", "order_id", "customer_id", "valor", "status"],
        [(t, o, c, "100.00", s) for t, o, c, s in PAGAMENTOS],
    )
    _escrever(
        origem,
        "clientes",
        [
            "customer_id",
            "canal_preferido",
            "aceita_comunicacao_whatsapp",
            "aceita_comunicacao_email",
        ],
        CLIENTES,
    )
    _escrever(
        origem,
        "historico_conversas",
        ["conversation_id", "customer_id", "order_id", "data_abertura"],
        [(c, cl, o, "2026-10-01 10:00:00") for c, cl, o in CONVERSAS],
    )
    caminho = tmp_path / "base.db"
    carregar(origem, caminho)
    return Base(caminho)


def _por_tipo(padroes: list[Padrao]) -> dict[str, Padrao]:
    return {p.tipo: p for p in padroes}


def test_HG_17_detecta_cobranca_em_dobro_sem_estorno(base):
    padrao = _por_tipo(detectar_padroes(base))["cobranca_em_dobro"]
    assert padrao.escopo == ("P1", "P3", "P5")
    assert padrao.evidencia["contagem"] == 3
    assert "pagamentos_gateway" in padrao.evidencia["consulta"]
    assert padrao.clientes == {"P1": "C1", "P3": "C3", "P5": "C5"}


def test_HG_17_detecta_contato_repetido_por_cliente_e_pedido(base):
    padrao = _por_tipo(detectar_padroes(base))["contato_repetido"]
    assert padrao.escopo == ("P1", "P4")
    assert padrao.evidencia["contagem"] == 2
    assert padrao.evidencia["conversas"] == 5
    assert padrao.conversation_ids == ("AT1", "AT2", "AT4", "AT5", "AT6")


@pytest.mark.parametrize(
    ("cliente", "esperado"),
    [
        (
            {
                "canal_preferido": "whatsapp",
                "aceita_comunicacao_whatsapp": "sim",
                "aceita_comunicacao_email": "sim",
            },
            "whatsapp",
        ),
        (
            {
                "canal_preferido": "whatsapp",
                "aceita_comunicacao_whatsapp": "não",
                "aceita_comunicacao_email": "sim",
            },
            "email",
        ),
        (
            {
                "canal_preferido": "email",
                "aceita_comunicacao_whatsapp": "sim",
                "aceita_comunicacao_email": "não",
            },
            "whatsapp",
        ),
        (
            {
                "canal_preferido": "whatsapp",
                "aceita_comunicacao_whatsapp": "não",
                "aceita_comunicacao_email": "não",
            },
            None,
        ),
    ],
)
def test_HG_23_canal_so_com_consentimento(cliente, esperado):
    assert canal_com_consentimento(cliente) == esperado


def test_HG_17_HG_23_tratar_abre_incidente_e_notifica_so_quem_consentiu(base):
    analista = Analista(base, Ferramentas(base))
    padrao = _por_tipo(detectar_padroes(base))["cobranca_em_dobro"]
    resultado = analista.tratar(padrao)

    assert resultado.incidente["ferramenta"] == "abrir_incidente"
    assert resultado.incidente["tipo"] == "cobranca_em_dobro"
    assert resultado.incidente["escopo"] == ("P1", "P3", "P5")
    assert resultado.incidente["papel"] == "analista"
    enviados = {n["order_id"]: n["canal"] for n in resultado.notificacoes}
    assert enviados == {"P1": "whatsapp", "P3": "email"}
    assert resultado.sem_consentimento == ("P5",)
    assert resultado.adiados == ()
    # o time fica sabendo pelo canal (acionar_pessoa, ferramenta do W1, papel analista)
    assert resultado.aviso_ao_time is not None
    assert resultado.aviso_ao_time.executado_por == "agente_analista"


def test_HG_17_respeita_maximo_de_notificacoes_por_dia(base):
    analista = Analista(base, Ferramentas(base), max_por_dia=1)
    padrao = _por_tipo(detectar_padroes(base))["cobranca_em_dobro"]
    resultado = analista.tratar(padrao)
    assert len(resultado.notificacoes) == 1
    assert resultado.adiados == ("P3",)
    # o limite é por dia: um segundo padrão no mesmo dia não envia nada
    segundo = analista.tratar(padrao)
    assert segundo.notificacoes == ()


def test_HG_17_limite_diario_vem_de_ferramentas_csv(base):
    assert Analista(base, Ferramentas(base)).max_por_dia == 300


def test_HG_17_contato_repetido_abre_incidente_sem_notificar(base):
    """Com 3 pedidos, o mínimo do Q22 (SPEC.md) para abrir incidente."""
    analista = Analista(base, Ferramentas(base))
    detectado = _por_tipo(detectar_padroes(base))["contato_repetido"]
    padrao = Padrao(
        tipo=detectado.tipo,
        fator=detectado.fator,
        escopo=("P1", "P2", "P4"),
        evidencia=detectado.evidencia,
        clientes={"P1": "C1", "P2": "C2", "P4": "C4"},
    )
    resultado = analista.tratar(padrao)
    assert resultado.incidente["tipo"] == "contato_repetido"
    assert resultado.notificacoes == ()


def test_HG_19_atendimento_chama_analista_com_pedido_do_caso(base):
    resultado = chamar_analista(
        base,
        Ferramentas(base),
        fator="cobranca_em_dobro",
        order_ids=["P3"],
        conversation_ids=["AT7"],
    )
    assert resultado.padrao.tipo == "cobranca_em_dobro"
    assert "P3" in resultado.padrao.escopo
    assert resultado.incidente["origem"] == {
        "conversation_ids": ("AT7",),
        "order_ids": ("P3",),
        "fator": "cobranca_em_dobro",
    }


def test_HG_19_sem_padrao_confirmado_o_analista_nao_abre_incidente(base):
    resultado = chamar_analista(
        base, Ferramentas(base), fator="cobranca_em_dobro", order_ids=["P4"]
    )
    assert resultado.padrao is None
    assert resultado.incidente is None


def test_HG_19_analista_age_so_com_ferramentas_do_papel_analista(base):
    resultado = chamar_analista(
        base, Ferramentas(base), fator="cobranca_em_dobro", order_ids=["P1"]
    )
    papeis = {resultado.incidente["papel"]} | {n["papel"] for n in resultado.notificacoes}
    assert papeis == {"analista"}
    catalogo = base.ferramentas()
    for nome in ("abrir_incidente", "notificar_clientes", "acionar_pessoa"):
        assert "analista" in catalogo[nome]["papeis_permitidos"]


@pytest.mark.integracao
def test_HG_17_base_real_bate_com_baseline_m4_m7(tmp_path):
    raiz = Path(__file__).resolve().parents[1]
    caminho = tmp_path / "base.db"
    carregar(raiz / "docs", caminho)
    padroes = _por_tipo(detectar_padroes(Base(caminho)))
    assert padroes["cobranca_em_dobro"].evidencia["contagem"] == 12  # M7
    assert padroes["contato_repetido"].evidencia["contagem"] == 453  # M4
    assert padroes["contato_repetido"].evidencia["conversas"] == 982  # M4


def test_HG_17_incidente_e_avisos_ficam_no_log_de_acoes(base):
    ferramentas = Ferramentas(base)
    resultado = Analista(base, ferramentas).tratar(
        _por_tipo(detectar_padroes(base))["cobranca_em_dobro"]
    )
    registros = ferramentas.acoes_registradas()
    incidentes = [r for r in registros if r.acao == "abrir_incidente"]
    avisos = [r for r in registros if r.acao == "notificar_clientes"]
    assert [r.referencia_sistema for r in incidentes] == [resultado.incidente["incidente_id"]]
    assert resultado.incidente["incidente_id"].startswith("INC-")
    assert sorted(r.order_id for r in avisos) == ["P1", "P3"]
    assert {n["referencia"] for n in resultado.notificacoes} == {
        r.referencia_sistema for r in avisos
    }
    assert {r.executado_por for r in incidentes + avisos} == {"agente_analista"}


# ---------- Q22: um incidente por (tipo, dia), sem reaviso, sem promessa ----------


def _contar(ferramentas, acao):
    return sum(1 for r in ferramentas.acoes_registradas() if r.acao == acao)


def test_HG_17_Q22_mesmo_padrao_no_mesmo_dia_reaproveita_o_incidente(base):
    ferramentas = Ferramentas(base)
    analista = Analista(base, ferramentas)
    padrao = _por_tipo(detectar_padroes(base))["cobranca_em_dobro"]
    primeiro = analista.tratar(padrao)
    segundo = analista.tratar(padrao)
    assert segundo.incidente["incidente_id"] == primeiro.incidente["incidente_id"]
    assert segundo.detalhes["reaproveitado"] is True
    assert segundo.notificacoes == ()
    assert _contar(ferramentas, "abrir_incidente") == 1
    assert _contar(ferramentas, "notificar_clientes") == 2  # P1 e P3, uma vez cada


def test_HG_17_Q22_outro_dia_abre_outro_incidente(base):
    ferramentas = Ferramentas(base)
    analista = Analista(base, ferramentas)
    padrao = _por_tipo(detectar_padroes(base))["cobranca_em_dobro"]
    hoje = analista.tratar(padrao)
    amanha = analista.tratar(padrao, agora=datetime(2026, 11, 3, 9, 0, tzinfo=FUSO))
    assert amanha.incidente["incidente_id"] != hoje.incidente["incidente_id"]


def test_HG_17_Q22_padrao_com_menos_de_3_pedidos_nao_abre_incidente(base):
    ferramentas = Ferramentas(base)
    padrao = Padrao(
        tipo="cobranca_em_dobro",
        fator="teste",
        escopo=("P1", "P3"),
        evidencia={"consulta": "teste", "contagem": 2},
        clientes={"P1": "C1", "P3": "C3"},
    )
    resultado = Analista(base, ferramentas).tratar(padrao)
    assert resultado.incidente is None
    assert resultado.notificacoes == ()
    assert "3" in resultado.detalhes["motivo"]
    assert _contar(ferramentas, "abrir_incidente") == 0


def test_HG_17_Q22_aviso_nao_promete_acao_nao_executada(base):
    resultado = Analista(base, Ferramentas(base)).tratar(
        _por_tipo(detectar_padroes(base))["cobranca_em_dobro"]
    )
    for notificacao in resultado.notificacoes:
        texto = notificacao["texto"].lower()
        assert "estorno" not in texto and "reembols" not in texto
        assert "análise" in texto


@pytest.mark.integracao
def test_HG_17_Q22_fila_e_router_na_base_real_abrem_1_incidente_e_11_avisos(tmp_path):
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from atendimento.api.analista import criar_router

    raiz = Path(__file__).resolve().parents[1]
    caminho = tmp_path / "base.db"
    carregar(raiz / "docs", caminho)
    base = Base(caminho)
    ferramentas = Ferramentas(base)
    analista = Analista(base, ferramentas)
    escopo = _por_tipo(detectar_padroes(base))["cobranca_em_dobro"].escopo
    # vários casos da fila chamam o analista, cada um com o seu pedido
    for order_id in escopo[:5]:
        chamar_analista(
            base, ferramentas, fator="cobranca_em_dobro", order_ids=[order_id], analista=analista
        )
    # e depois alguém aciona a rota do analista
    contexto = SimpleNamespace(base=base, ferramentas=ferramentas, obter_analista=lambda: analista)
    app = FastAPI()
    app.include_router(criar_router(lambda: contexto))
    resposta = TestClient(app).post("/api/analista/padroes/cobranca_em_dobro/tratar")
    assert resposta.status_code == 200
    assert resposta.json()["ja_tratado"] is True
    assert _contar(ferramentas, "abrir_incidente") == 1
    assert _contar(ferramentas, "notificar_clientes") == 11
