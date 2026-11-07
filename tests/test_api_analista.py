"""Rotas do agente analista (HG-17, HG-19, HG-23) num FastAPI só com o router."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from atendimento.api.analista import criar_router
from atendimento.dados.carga import carregar
from atendimento.dados.repositorio import Base
from atendimento.ferramentas import Ferramentas

FIXTURES_W1 = Path(__file__).parent / "fixtures" / "dados"


def _escrever(pasta: Path, nome: str, cabecalho: list[str], linhas: list[tuple]) -> None:
    with open(pasta / f"{nome}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cabecalho)
        w.writerows(linhas)


@pytest.fixture
def contexto(tmp_path):
    origem = tmp_path / "csv"
    shutil.copytree(FIXTURES_W1, origem)
    _escrever(
        origem,
        "pagamentos_gateway",
        ["transacao_id", "order_id", "customer_id", "valor", "status"],
        [
            ("T1", "P1", "C1", "100.00", "capturada"),
            ("T2", "P1", "C1", "100.00", "capturada"),
            ("T3", "P2", "C2", "100.00", "paga"),
            ("T4", "P2", "C2", "100.00", "capturada"),
            ("T5", "P3", "C1", "100.00", "capturada"),
            ("T6", "P3", "C1", "100.00", "capturada"),
        ],
    )
    _escrever(
        origem,
        "clientes",
        [
            "customer_id",
            "canal_preferido",
            "aceita_comunicacao_whatsapp",
            "aceita_comunicacao_email",
            "cpf",
            "email",
            "telefone",
        ],
        [
            ("C1", "whatsapp", "sim", "sim", "123.456.789-01", "c1@exemplo.com", "(11) 91234-5678"),
            ("C2", "email", "não", "não", "987.654.321-09", "c2@exemplo.com", "(11) 98765-4321"),
        ],
    )
    _escrever(
        origem,
        "historico_conversas",
        ["conversation_id", "customer_id", "order_id", "data_abertura"],
        [("AT1", "C1", "P1", "2026-10-01 10:00:00"), ("AT2", "C1", "P1", "2026-10-02 10:00:00")],
    )
    caminho = tmp_path / "base.db"
    carregar(origem, caminho)
    base = Base(caminho)
    eventos: list[dict] = []
    canal: list[dict] = []
    return SimpleNamespace(
        base=base,
        ferramentas=Ferramentas(base),
        eventos=eventos,
        canal=canal,
        emitir=lambda tipo, payload: eventos.append({"tipo": tipo, "payload": payload}),
        postar_no_canal=lambda tipo, para, texto, cid, **extra: canal.append(
            {"tipo": tipo, "para": para, "texto": texto, "conversation_id": cid, **extra}
        ),
    )


@pytest.fixture
def cliente(contexto):
    app = FastAPI()
    app.include_router(criar_router(lambda: contexto))
    return TestClient(app)


def test_HG_17_lista_padroes_com_escopo_e_evidencia(cliente):
    resposta = cliente.get("/api/analista/padroes")
    assert resposta.status_code == 200
    padroes = {p["tipo"]: p for p in resposta.json()}
    assert padroes["cobranca_em_dobro"]["escopo"] == ["P1", "P2", "P3"]
    assert padroes["cobranca_em_dobro"]["evidencia"]["contagem"] == 3
    assert padroes["contato_repetido"]["conversation_ids"] == ["AT1", "AT2"]


def test_HG_17_tratar_abre_incidente_publica_evento_e_avisa_canal(cliente, contexto):
    resposta = cliente.post("/api/analista/padroes/cobranca_em_dobro/tratar")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["incidente"]["incidente_id"].startswith("INC-")
    assert [n["order_id"] for n in corpo["notificacoes"]] == ["P1", "P3"]
    assert corpo["sem_consentimento"] == ["P2"]  # HG-23
    assert [e["tipo"] for e in contexto.eventos] == ["incidente"]
    assert contexto.eventos[0]["payload"]["incidente_id"] == corpo["incidente"]["incidente_id"]
    assert len(contexto.canal) == 1


def test_HG_17_segunda_chamada_nao_abre_outro_incidente(cliente, contexto):
    primeira = cliente.post("/api/analista/padroes/cobranca_em_dobro/tratar").json()
    segunda = cliente.post("/api/analista/padroes/cobranca_em_dobro/tratar").json()
    assert segunda["incidente"]["incidente_id"] == primeira["incidente"]["incidente_id"]
    assert segunda["ja_tratado"] is True
    incidentes = [
        r for r in contexto.ferramentas.acoes_registradas() if r.acao == "abrir_incidente"
    ]
    assert len(incidentes) == 1


def test_HG_19_tipo_inexistente_devolve_404(cliente):
    assert cliente.post("/api/analista/padroes/nao_existe/tratar").status_code == 404


def test_HG_23_resposta_nao_expoe_dado_pessoal(cliente):
    texto = cliente.get("/api/analista/padroes").text
    texto += cliente.post("/api/analista/padroes/cobranca_em_dobro/tratar").text
    for dado in ("123.456.789-01", "c1@exemplo.com", "91234-5678"):
        assert dado not in texto
