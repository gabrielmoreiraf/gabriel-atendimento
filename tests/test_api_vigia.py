"""Rotas do vigia (HG-20, HG-21) num FastAPI só com o router."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from atendimento.api.vigia import criar_router
from atendimento.dados.carga import carregar
from atendimento.dados.repositorio import Base
from atendimento.ferramentas import Ferramentas

FIXTURES_W1 = Path(__file__).parent / "fixtures" / "dados"


@pytest.fixture
def contexto(tmp_path):
    origem = tmp_path / "csv"
    shutil.copytree(FIXTURES_W1, origem)
    with open(origem / "fila_aberta.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "conversation_id",
                "customer_id",
                "order_id",
                "canal",
                "data_abertura",
                "status",
                "atendente_id",
                "data_primeira_resposta",
                "assunto",
            ]
        )
        w.writerow(
            [
                "WA1",
                "CH1",
                "P1",
                "whatsapp",
                "2026-11-02 03:00:00",
                "aberta",
                "atendente_01",
                "",
                "Cadê?",
            ]
        )
        w.writerow(["WA2", "CH2", "P2", "whatsapp", "2026-11-02 03:00:00", "aberta", "", "", "Oi"])
        w.writerow(["EM1", "CH3", "P3", "email", "2026-11-01 07:00:00", "aberta", "", "", "Ajuda"])
    caminho = tmp_path / "base.db"
    carregar(origem, caminho)
    base = Base(caminho)
    acao = {
        "ferramenta": "reembolsar",
        "executado_por": "agente",
        "order_id": "P1",
        "conversation_id": "WA1",
        "papel": "atendente",
    }
    with base.conexao:
        base.conexao.execute(
            "INSERT INTO aprovacoes (aprovacao_id, acao, solicitado_por, estado, solicitado_em) "
            "VALUES (?, ?, ?, 'pendente', ?)",
            ("APR-000001", json.dumps(acao), "agente", "2026-11-02 08:00:00"),
        )
    eventos: list[dict] = []
    canal: list[dict] = []
    return SimpleNamespace(
        base=base,
        ferramentas=Ferramentas(base),
        casos={"WA2": object()},  # já tratada pelo agente: não gera aviso
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


def test_HG_20_alertas_padrao_e_no_agora_do_projeto(cliente):
    corpo = cliente.get("/api/vigia/alertas").json()
    assert corpo["agora"].startswith("2026-11-02T08:00:00")
    assert [a["conversation_id"] for a in corpo["sla"]] == ["EM1"]  # WA1 vence 08:30
    assert corpo["aprovacoes"] == []  # parada há 0 h


def test_HG_20_alertas_em_outro_agora_ignora_conversa_ja_tratada(cliente):
    corpo = cliente.get("/api/vigia/alertas", params={"agora": "2026-11-02T08:25:00"}).json()
    sla = {a["conversation_id"]: a for a in corpo["sla"]}
    assert set(sla) == {"EM1", "WA1"}
    assert sla["WA1"]["minutos_restantes"] == 5
    assert sla["WA1"]["para"] == "atendente_01"


def test_HG_21_rodar_posta_no_canal_emite_evento_e_nao_duplica(cliente, contexto):
    params = {"agora": "2026-11-02T10:30:00"}
    primeira = cliente.post("/api/vigia/rodar", params=params).json()
    assert {p["chave"] for p in primeira["postados"]} == {
        "sla:EM1:estourado",
        "sla:WA1:estourado",
        "aprovacao:APR-000001:1",
    }
    tipos = {m["tipo"] for m in contexto.canal}
    assert tipos == {"aviso", "aprovacao"}
    lembrete = next(m for m in contexto.canal if m["tipo"] == "aprovacao")
    assert lembrete["conversation_id"] == "WA1"
    assert lembrete["para"] in {"supervisor_01", "supervisor_02", "supervisor_03"}
    assert [e["tipo"] for e in contexto.eventos] == ["vigia"]

    segunda = cliente.post("/api/vigia/rodar", params=params).json()
    assert segunda["postados"] == []
    assert segunda["ja_postados"] == 3
    assert len(contexto.canal) == 3


def test_HG_20_agora_invalido_devolve_422(cliente):
    assert cliente.get("/api/vigia/alertas", params={"agora": "ontem"}).status_code == 422


def test_HG_21_lembrete_avisa_o_cliente_uma_vez_por_lembrete(cliente, contexto):
    for _ in range(2):
        cliente.post("/api/vigia/rodar", params={"agora": "2026-11-02T10:30:00"})
    respostas = [
        r for r in contexto.ferramentas.acoes_registradas() if r.acao == "responder_cliente"
    ]
    assert [r.conversation_id for r in respostas] == ["WA1"]
    # novo nível de lembrete (2 h depois) avisa de novo
    cliente.post("/api/vigia/rodar", params={"agora": "2026-11-02T12:30:00"})
    respostas = [
        r for r in contexto.ferramentas.acoes_registradas() if r.acao == "responder_cliente"
    ]
    assert len(respostas) == 2
