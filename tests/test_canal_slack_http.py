"""Slack em modo HTTP para o Vercel (ADR-002, contrato 3): endpoint assinado, sem thread.

Sem rede: cliente Slack falso injetado no App do Bolt; assinatura gerada com o
SignatureVerifier do slack_sdk.
"""

from __future__ import annotations

import json
import sqlite3
import time
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fixtures.agente.falsos import BaseFalsa, FerramentasFalsas, anexo, captura, pedido
from slack_sdk import WebClient
from slack_sdk.signature import SignatureVerifier

from atendimento.agente.caso import Agente
from atendimento.api.slack import criar_router
from atendimento.canal_slack import (
    CanalSlack,
    RegistroBanco,
    RegistroMemoria,
    config_do_ambiente,
    criar_gancho,
    iniciar,
)

SEGREDO = "segredo-de-teste"
AMBIENTE_HTTP = {
    "ATENDIMENTO_SLACK": "1",
    "ATENDIMENTO_SLACK_MODO": "http",
    "SLACK_BOT_TOKEN": "xoxb-falso",
    "SLACK_SIGNING_SECRET": SEGREDO,
    "SLACK_CANAL_ID": "C0TIME",
    "SLACK_SUPERVISORES": "U0SUP1:supervisor_01,U0SUP2:supervisor_02",
}


class WebClientFalso(WebClient):
    def __init__(self):
        super().__init__(token="xoxb-falso")
        self.postadas: list[dict] = []
        self.atualizadas: list[dict] = []
        self.efemeras: list[dict] = []

    def chat_postMessage(self, **kw):
        self.postadas.append(kw)
        return {"ok": True, "ts": f"1700.{len(self.postadas):04d}", "channel": kw.get("channel")}

    def chat_update(self, **kw):
        self.atualizadas.append(kw)
        return {"ok": True}

    def chat_postEphemeral(self, **kw):
        self.efemeras.append(kw)
        return {"ok": True}

    def auth_test(self, **kw):  # o Bolt autoriza o time na primeira requisição
        from slack_sdk.web import SlackResponse

        dados = {"ok": True, "user_id": "U0FIO", "bot_id": "B0FIO", "team_id": "T0", "url": ""}
        return SlackResponse(
            client=self,
            http_verb="POST",
            api_url="auth.test",
            req_args={},
            data=dados,
            headers={},
            status_code=200,
        )


def _agente_com_aprovacao():
    base = BaseFalsa()
    base.conversa("AT1", ["O pote chegou amassado e vazou tudo."], order_id="GBH000002")
    base.com_pedido(pedido("GBH000002", valor=260.0))
    base.com_anexo(anexo("AT1", "GBH000002", captura=captura(31)))
    agente = Agente(base, FerramentasFalsas(base))
    agente.processar("AT1")
    aprovacao_id = next(m for m in agente.canal if m["tipo"] == "aprovacao")["aprovacao_id"]
    return agente, aprovacao_id


# ---------- configuração ----------


def test_P5_modo_padrao_http_no_vercel_e_socket_local():
    socket = {k: v for k, v in AMBIENTE_HTTP.items() if k != "ATENDIMENTO_SLACK_MODO"}
    socket["SLACK_APP_TOKEN"] = "xapp-falso"
    assert config_do_ambiente(socket).modo == "socket"
    assert config_do_ambiente({**socket, "VERCEL": "1"}).modo == "http"
    assert config_do_ambiente(AMBIENTE_HTTP).modo == "http"


def test_P5_http_exige_signing_secret_e_dispensa_app_token():
    assert config_do_ambiente(AMBIENTE_HTTP) is not None  # sem SLACK_APP_TOKEN
    sem_segredo = {k: v for k, v in AMBIENTE_HTTP.items() if k != "SLACK_SIGNING_SECRET"}
    assert config_do_ambiente(sem_segredo) is None
    assert SEGREDO not in repr(config_do_ambiente(AMBIENTE_HTTP))


def test_P5_modo_http_nao_abre_thread_de_socket():
    agente, _ = _agente_com_aprovacao()
    assert iniciar(agente, ambiente=AMBIENTE_HTTP) is None


# ---------- registro do ts (memória e banco) ----------


class BancoSqlite:
    """Só o contrato do W3 que o registro usa: executar(sql com ?, params) -> list[dict]."""

    dialeto = "sqlite"

    def __init__(self):
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row

    def executar(self, sql, params=()):
        cursor = self.con.execute(sql, params)
        self.con.commit()
        return [dict(linha) for linha in cursor.fetchall()]


@pytest.mark.parametrize("fabrica", [RegistroMemoria, lambda: RegistroBanco(BancoSqlite())])
def test_P5_registro_guarda_ts_estado_incidentes_e_placar(fabrica):
    registro = fabrica()
    assert registro.mensagem("CANAL-0001") is None
    registro.salvar_mensagem("CANAL-0001", "1700.0001", "pendente")
    registro.salvar_mensagem("CANAL-0001", "1700.0001", "aprovada")
    assert registro.mensagem("CANAL-0001") == {"ts": "1700.0001", "estado": "aprovada"}
    assert registro.mensagem_por_ts("1700.0001") == "CANAL-0001"
    assert registro.marcar_incidente("INC-000001") is True
    assert registro.marcar_incidente("INC-000001") is False
    assert registro.ultimo_placar() is None
    registro.salvar_placar({"resolvidas_sozinho": 1})
    assert registro.ultimo_placar() == {"resolvidas_sozinho": 1}


def test_P5_registro_no_banco_sobrevive_a_uma_nova_instancia():
    banco = BancoSqlite()
    RegistroBanco(banco).salvar_mensagem("CANAL-0001", "1700.0001", "pendente")
    assert RegistroBanco(banco).mensagem("CANAL-0001")["ts"] == "1700.0001"


# ---------- gancho: postagem na mesma requisição ----------


def test_P5_gancho_posta_ao_gravar_e_atualiza_ao_mudar_estado_sem_thread():
    agente, aprovacao_id = _agente_com_aprovacao()
    cliente = WebClientFalso()
    registro = RegistroMemoria()
    gancho = criar_gancho(agente, ambiente=AMBIENTE_HTTP, cliente=cliente, registro=registro)
    mensagem = next(m for m in agente.canal if m.get("aprovacao_id") == aprovacao_id)
    gancho.mensagem_gravada(mensagem)
    gancho.mensagem_gravada(mensagem)  # gravada de novo sem mudança: não duplica
    assert len(cliente.postadas) == 1
    assert registro.mensagem(mensagem["id"])["ts"] == "1700.0001"
    agente.aprovar(aprovacao_id, "supervisor_02", "ok")
    gancho.mensagem_gravada(mensagem)  # estado mudou: chat_update na mesma requisição
    assert cliente.atualizadas and cliente.atualizadas[-1]["ts"] == "1700.0001"


def test_P5_gancho_ignora_rotina_e_posta_resumo_da_rodada_uma_vez():
    agente, _ = _agente_com_aprovacao()
    cliente = WebClientFalso()
    gancho = criar_gancho(agente, ambiente=AMBIENTE_HTTP, cliente=cliente)
    gancho.mensagem_gravada(
        {"id": "CANAL-0099", "tipo": "aviso", "texto": "AT1: informar_status executado"}
    )
    assert cliente.postadas == []
    placar = agente.placar()
    gancho.rodada_terminada(placar)
    gancho.rodada_terminada(placar)
    assert len(cliente.postadas) == 1
    assert cliente.postadas[0]["text"].startswith("Rodada das")


def test_P5_gancho_desligado_sem_configuracao():
    agente, _ = _agente_com_aprovacao()
    assert criar_gancho(agente, ambiente={}) is None


def test_P5_falha_do_slack_no_gancho_nao_quebra_a_requisicao():
    agente, aprovacao_id = _agente_com_aprovacao()

    class Quebrado(WebClientFalso):
        def chat_postMessage(self, **kw):
            raise ConnectionError("sem rede")

    gancho = criar_gancho(agente, ambiente=AMBIENTE_HTTP, cliente=Quebrado())
    mensagem = next(m for m in agente.canal if m.get("aprovacao_id") == aprovacao_id)
    gancho.mensagem_gravada(mensagem)  # não levanta
    assert gancho.canal.falhas


# ---------- endpoint /api/slack/eventos ----------


def _assinado(corpo: str, *, segredo: str = SEGREDO, content_type: str) -> dict:
    ts = str(int(time.time()))
    assinatura = SignatureVerifier(segredo).generate_signature(timestamp=ts, body=corpo)
    return {
        "X-Slack-Request-Timestamp": ts,
        "X-Slack-Signature": assinatura,
        "Content-Type": content_type,
    }


@pytest.fixture
def ambiente_http(monkeypatch):
    for chave, valor in AMBIENTE_HTTP.items():
        monkeypatch.setenv(chave, valor)
    monkeypatch.delenv("SLACK_APP_TOKEN", raising=False)
    # o Bolt autoriza o time com auth.test no WebClient que cria por requisição: sem rede aqui
    falso = WebClientFalso()
    monkeypatch.setattr(WebClient, "auth_test", lambda self, **kw: falso.auth_test())


def _cliente_http(agente, slack):
    app = FastAPI()
    app.include_router(criar_router(lambda: agente, cliente=slack))
    return TestClient(app)


def _clique(action_id, valor, usuario="U0SUP1"):
    payload = {
        "type": "block_actions",
        "team": {"id": "T0"},
        "user": {"id": usuario},
        "api_app_id": "A0",
        "token": "x",
        "container": {"type": "message", "message_ts": "1700.0001", "channel_id": "C0TIME"},
        "trigger_id": "1.2",
        "channel": {"id": "C0TIME"},
        "message": {"ts": "1700.0001", "text": "x"},
        "response_url": "https://hooks.slack.invalid/x",
        "actions": [
            {
                "type": "button",
                "action_id": action_id,
                "block_id": "b1",
                "value": valor,
                "action_ts": "1.3",
            }
        ],
    }
    return urlencode({"payload": json.dumps(payload)})


def test_P5_url_verification_responde_o_challenge(ambiente_http):
    agente, _ = _agente_com_aprovacao()
    corpo = json.dumps({"type": "url_verification", "challenge": "abc123", "token": "x"})
    resposta = _cliente_http(agente, WebClientFalso()).post(
        "/api/slack/eventos",
        content=corpo,
        headers=_assinado(corpo, content_type="application/json"),
    )
    assert resposta.status_code == 200
    assert "abc123" in resposta.text


def test_P5_assinatura_invalida_e_recusada(ambiente_http):
    agente, aprovacao_id = _agente_com_aprovacao()
    corpo = _clique("fio_aprovar", aprovacao_id)
    cabecalhos = _assinado(
        corpo, segredo="outro-segredo", content_type="application/x-www-form-urlencoded"
    )
    resposta = _cliente_http(agente, WebClientFalso()).post(
        "/api/slack/eventos", content=corpo, headers=cabecalhos
    )
    assert resposta.status_code == 401
    assert agente.aprovacoes[aprovacao_id].estado == "pendente"


def test_HP_10_aprovar_pelo_botao_via_http(ambiente_http):
    agente, aprovacao_id = _agente_com_aprovacao()
    slack = WebClientFalso()
    corpo = _clique("fio_aprovar", aprovacao_id)
    inicio = time.monotonic()
    resposta = _cliente_http(agente, slack).post(
        "/api/slack/eventos",
        content=corpo,
        headers=_assinado(corpo, content_type="application/x-www-form-urlencoded"),
    )
    assert resposta.status_code == 200
    assert time.monotonic() - inicio < 3  # ack dentro do prazo do Slack
    assert agente.aprovacoes[aprovacao_id].estado == "aprovada"
    assert slack.atualizadas and "supervisor_01" in slack.atualizadas[-1]["text"]


def test_HG_03_autoaprovacao_via_http_vira_efemera(ambiente_http):
    agente, aprovacao_id = _agente_com_aprovacao()
    agente.aprovacoes[aprovacao_id].solicitado_por = "supervisor_01"
    slack = WebClientFalso()
    corpo = _clique("fio_aprovar", aprovacao_id)
    _cliente_http(agente, slack).post(
        "/api/slack/eventos",
        content=corpo,
        headers=_assinado(corpo, content_type="application/x-www-form-urlencoded"),
    )
    assert agente.aprovacoes[aprovacao_id].estado == "pendente"
    assert "própria" in slack.efemeras[-1]["text"]


def test_HG_10_mencao_via_http_responde_na_thread(ambiente_http):
    agente, _ = _agente_com_aprovacao()
    slack = WebClientFalso()
    corpo = json.dumps(
        {
            "token": "x",
            "team_id": "T0",
            "api_app_id": "A0",
            "type": "event_callback",
            "event_id": "Ev1",
            "event_time": 1,
            "event": {
                "type": "app_mention",
                "user": "U0ATD",
                "text": "<@U0FIO> status do pedido GBH000002",
                "ts": "1700.0009",
                "channel": "C0TIME",
            },
        }
    )
    resposta = _cliente_http(agente, slack).post(
        "/api/slack/eventos",
        content=corpo,
        headers=_assinado(corpo, content_type="application/json"),
    )
    assert resposta.status_code == 200
    assert slack.postadas and slack.postadas[-1]["thread_ts"] == "1700.0009"
    assert "GBH000002" in slack.postadas[-1]["text"]


def test_P5_endpoint_sem_configuracao_http_responde_404(monkeypatch):
    monkeypatch.setenv("ATENDIMENTO_SLACK", "0")
    agente, _ = _agente_com_aprovacao()
    resposta = _cliente_http(agente, WebClientFalso()).post("/api/slack/eventos", content="{}")
    assert resposta.status_code == 404


def test_P5_canal_slack_aceita_registro_injetado():
    agente, _ = _agente_com_aprovacao()
    registro = RegistroMemoria()
    canal = CanalSlack(
        agente, WebClientFalso(), config_do_ambiente(AMBIENTE_HTTP), registro=registro
    )
    canal.sincronizar()
    assert registro.mensagem(agente.canal[0]["id"]) is not None


@pytest.fixture(
    params=[
        pytest.param("sqlite", id="sqlite"),
        pytest.param("postgres", id="postgres", marks=pytest.mark.postgres),
    ]
)
def banco_real(request, tmp_path):
    from atendimento.dados.banco import conectar

    if request.param == "sqlite":
        banco = conectar(str(tmp_path / "slack.db"))
        yield banco
        banco.fechar()
    else:
        from tests_postgres import banco_postgres_temporario

        with banco_postgres_temporario() as banco:
            yield banco


def test_P5_registro_no_banco_do_w3_sqlite_e_postgres(banco_real):
    registro = RegistroBanco(banco_real)
    registro.salvar_mensagem("CANAL-0001", "1700.0001", "pendente")
    registro.salvar_mensagem("CANAL-0001", "1700.0001", "aprovada")
    outro = RegistroBanco(banco_real)  # outra requisição, outra instância
    assert outro.mensagem("CANAL-0001") == {"ts": "1700.0001", "estado": "aprovada"}
    assert outro.mensagem_por_ts("1700.0001") == "CANAL-0001"
    assert outro.marcar_incidente("INC-000001") is True
    assert RegistroBanco(banco_real).marcar_incidente("INC-000001") is False
    outro.salvar_placar({"resolvidas_sozinho": 34, "custo_evitado_rs": 636.0})
    assert RegistroBanco(banco_real).ultimo_placar() == {
        "resolvidas_sozinho": 34,
        "custo_evitado_rs": 636.0,
    }
