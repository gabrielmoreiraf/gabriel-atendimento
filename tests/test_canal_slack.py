"""Canal do time no Slack (P5, HP-10, HG-10, HG-20). Sem rede: cliente Slack falso."""

from __future__ import annotations

import pytest
from fixtures.agente.falsos import BaseFalsa, FerramentasFalsas, anexo, captura, pedido

from atendimento.agente.aprovacoes import AprovacaoRecusada
from atendimento.agente.caso import Agente
from atendimento.canal_slack import (
    CanalSlack,
    ConfigSlack,
    config_do_ambiente,
    iniciar,
    registrar_handlers,
)

TOKENS = {
    "ATENDIMENTO_SLACK": "1",
    "SLACK_BOT_TOKEN": "xoxb-falso",
    "SLACK_APP_TOKEN": "xapp-falso",
    "SLACK_CANAL_ID": "C0TIME",
    "SLACK_SUPERVISORES": "U0SUP1:supervisor_01, U0SUP2:supervisor_02",
}


class ClienteFalso:
    def __init__(self, falhar: bool = False):
        self.falhar = falhar
        self.postadas: list[dict] = []
        self.atualizadas: list[dict] = []
        self.efemeras: list[dict] = []

    def chat_postMessage(self, **kw):
        if self.falhar:
            raise ConnectionError("sem rede")
        self.postadas.append(kw)
        return {"ok": True, "ts": f"1700.{len(self.postadas):04d}", "channel": kw["channel"]}

    def chat_update(self, **kw):
        self.atualizadas.append(kw)
        return {"ok": True}

    def chat_postEphemeral(self, **kw):
        self.efemeras.append(kw)
        return {"ok": True}


def _agente_com_aprovacao():
    base = BaseFalsa()
    base.conversa("AT1", ["O pote chegou amassado e vazou tudo."], order_id="GBH000002")
    base.com_pedido(pedido("GBH000002", valor=260.0))
    base.com_anexo(anexo("AT1", "GBH000002", captura=captura(31)))
    agente = Agente(base, FerramentasFalsas(base))
    agente.processar("AT1")
    aprovacao_id = next(m for m in agente.canal if m["tipo"] == "aprovacao")["aprovacao_id"]
    return agente, aprovacao_id


def _canal(agente, cliente=None):
    config = config_do_ambiente(TOKENS)
    return CanalSlack(agente, cliente or ClienteFalso(), config)


def _clique(action_id, valor, usuario="U0SUP1", ts="1700.0001"):
    return {
        "user": {"id": usuario},
        "channel": {"id": "C0TIME"},
        "message": {"ts": ts},
        "actions": [{"action_id": action_id, "value": valor}],
    }


# ---------- configuração ----------


def test_P5_desligado_por_padrao():
    assert config_do_ambiente({}) is None
    assert (
        config_do_ambiente(
            {
                "ATENDIMENTO_SLACK": "0",
                **{k: v for k, v in TOKENS.items() if k != "ATENDIMENTO_SLACK"},
            }
        )
        is None
    )
    assert iniciar(object(), ambiente={}) is None


def test_P5_ligado_sem_tokens_nao_liga_nem_quebra():
    assert config_do_ambiente({"ATENDIMENTO_SLACK": "1"}) is None
    assert iniciar(object(), ambiente={"ATENDIMENTO_SLACK": "1"}) is None


def test_P5_config_mapeia_supervisores_e_nao_expoe_tokens():
    config = config_do_ambiente(TOKENS)
    assert isinstance(config, ConfigSlack)
    assert config.supervisores == {"U0SUP1": "supervisor_01", "U0SUP2": "supervisor_02"}
    assert "xoxb-falso" not in repr(config) and "xapp-falso" not in repr(config)


# ---------- espelho ----------


def test_HG_20_espelha_cada_mensagem_do_canal_uma_vez():
    agente, _ = _agente_com_aprovacao()
    cliente = ClienteFalso()
    canal = _canal(agente, cliente)
    canal.sincronizar()
    canal.sincronizar()
    assert len(cliente.postadas) == len(agente.canal)
    assert {p["channel"] for p in cliente.postadas} == {"C0TIME"}
    agente.postar_no_canal("aviso", None, "novo aviso", "AT1")
    canal.sincronizar()
    assert len(cliente.postadas) == len(agente.canal)


def test_HG_11_espelho_mascara_de_novo_por_garantia():
    agente, _ = _agente_com_aprovacao()
    agente.canal.append(
        {
            "id": "CANAL-9999",
            "tipo": "aviso",
            "para": None,
            "conversation_id": "AT1",
            "texto": "Cliente CPF 123.456.789-01, tel (11) 91234-5678, ana@exemplo.com",
        }
    )
    cliente = ClienteFalso()
    _canal(agente, cliente).sincronizar()
    enviado = str(cliente.postadas[-1])
    for dado in ("123.456.789-01", "91234-5678", "ana@exemplo.com"):
        assert dado not in enviado


def test_HP_10_aprovacao_vira_mensagem_com_botoes():
    agente, aprovacao_id = _agente_com_aprovacao()
    cliente = ClienteFalso()
    _canal(agente, cliente).sincronizar()
    msg = next(p for p in cliente.postadas if "aprova" in p["text"].lower())
    botoes = [e for b in msg["blocks"] if b["type"] == "actions" for e in b["elements"]]
    assert [(b["action_id"], b["value"]) for b in botoes] == [
        ("fio_aprovar", aprovacao_id),
        ("fio_rejeitar", aprovacao_id),
    ]
    assert "FIO pediu aprovação" in msg["text"]


def test_P5_falha_do_slack_nao_derruba_e_registra_motivo():
    agente, _ = _agente_com_aprovacao()
    canal = _canal(agente, ClienteFalso(falhar=True))
    canal.sincronizar()  # não levanta
    assert canal.falhas and "ConnectionError" in canal.falhas[-1]
    assert all("xoxb" not in f for f in canal.falhas)
    # o agente segue funcionando
    agente.postar_no_canal("aviso", None, "segue", "AT1")
    assert agente.canal[-1]["texto"] == "segue"


def test_HP_10_decisao_feita_na_interface_atualiza_a_mensagem_do_slack():
    agente, aprovacao_id = _agente_com_aprovacao()
    cliente = ClienteFalso()
    canal = _canal(agente, cliente)
    canal.sincronizar()
    agente.aprovar(aprovacao_id, "supervisor_02", "ok pela tela")
    canal.sincronizar()
    assert cliente.atualizadas
    atualizada = cliente.atualizadas[-1]
    assert not any(b["type"] == "actions" for b in atualizada["blocks"])


# ---------- botões ----------


def test_HP_10_aprovar_pelo_botao_chama_o_agente():
    agente, aprovacao_id = _agente_com_aprovacao()
    cliente = ClienteFalso()
    canal = _canal(agente, cliente)
    canal.sincronizar()
    canal.ao_clicar(_clique("fio_aprovar", aprovacao_id), cliente)
    assert agente.aprovacoes[aprovacao_id].estado == "aprovada"
    assert agente.aprovacoes[aprovacao_id].decidido_por == "supervisor_01"
    assert "supervisor_01" in cliente.atualizadas[-1]["text"]
    assert not cliente.efemeras


def test_HG_03_autoaprovacao_pelo_slack_e_recusada_com_efemera():
    agente, aprovacao_id = _agente_com_aprovacao()
    agente.aprovacoes[aprovacao_id].solicitado_por = "supervisor_01"
    cliente = ClienteFalso()
    canal = _canal(agente, cliente)
    canal.ao_clicar(_clique("fio_aprovar", aprovacao_id), cliente)
    assert agente.aprovacoes[aprovacao_id].estado == "pendente"
    assert cliente.efemeras and cliente.efemeras[-1]["user"] == "U0SUP1"
    assert "própria" in cliente.efemeras[-1]["text"]


def test_HP_10_rejeitar_pelo_botao_usa_justificativa_padrao():
    agente, aprovacao_id = _agente_com_aprovacao()
    cliente = ClienteFalso()
    _canal(agente, cliente).ao_clicar(_clique("fio_rejeitar", aprovacao_id, "U0SUP2"), cliente)
    aprovacao = agente.aprovacoes[aprovacao_id]
    assert (aprovacao.estado, aprovacao.decidido_por) == ("rejeitada", "supervisor_02")
    assert "Slack" in aprovacao.comentario


def test_HG_02_quem_nao_esta_no_mapa_nao_decide():
    agente, aprovacao_id = _agente_com_aprovacao()
    cliente = ClienteFalso()
    _canal(agente, cliente).ao_clicar(_clique("fio_aprovar", aprovacao_id, "U0ESTRANHO"), cliente)
    assert agente.aprovacoes[aprovacao_id].estado == "pendente"
    assert "não está autorizado" in cliente.efemeras[-1]["text"]


class AgenteSuspeita:
    """Só o que o canal usa de decidir_suspeita; as regras reais estão em test_agente_*."""

    def __init__(self, recusar: str | None = None):
        self.canal: list[dict] = []
        self.chamadas: list[tuple] = []
        self.recusar = recusar

    def decidir_suspeita(self, suspeita_id, supervisor_id, decisao, justificativa):
        if self.recusar:
            raise AprovacaoRecusada(self.recusar)
        self.chamadas.append((suspeita_id, supervisor_id, decisao, justificativa))


@pytest.mark.parametrize(
    ("action_id", "decisao"),
    [("fio_procedente", "procedente"), ("fio_improcedente", "improcedente")],
)
def test_HG_04_suspeita_decidida_pelo_botao(action_id, decisao):
    agente = AgenteSuspeita()
    cliente = ClienteFalso()
    _canal(agente, cliente).ao_clicar(_clique(action_id, "SUS-000001"), cliente)
    assert agente.chamadas == [("SUS-000001", "supervisor_01", decisao, "decidido pelo Slack")]
    assert decisao in cliente.atualizadas[-1]["text"]


def test_HG_04_quem_sinalizou_recebe_efemera():
    agente = AgenteSuspeita(recusar="Quem sinalizou a suspeita não a decide (HG-04).")
    cliente = ClienteFalso()
    _canal(agente, cliente).ao_clicar(_clique("fio_procedente", "SUS-000001"), cliente)
    assert "HG-04" in cliente.efemeras[-1]["text"]
    assert not cliente.atualizadas


def test_HG_04_suspeita_pendente_tem_botoes():
    agente = AgenteSuspeita()
    agente.canal.append(
        {
            "id": "CANAL-0001",
            "tipo": "suspeita",
            "para": "supervisor_01",
            "conversation_id": "AT1",
            "texto": "AT1: ação suspensa",
            "estado": "pendente",
            "suspeita_id": "SUS-000001",
        }
    )
    cliente = ClienteFalso()
    _canal(agente, cliente).sincronizar()
    botoes = [
        e for b in cliente.postadas[0]["blocks"] if b["type"] == "actions" for e in b["elements"]
    ]
    assert [b["action_id"] for b in botoes] == ["fio_procedente", "fio_improcedente"]


# ---------- HG-10: pedido de colaborador ----------


def test_HG_10_mencao_pergunta_status_do_pedido():
    agente, _ = _agente_com_aprovacao()
    canal = _canal(agente)
    resposta = canal.responder_mencao("<@U0FIO> qual o status do pedido GBH000002?", "U0ATD")
    assert "GBH000002" in resposta


def test_HG_10_pedido_de_colaborador_nao_muda_politica():
    agente, _ = _agente_com_aprovacao()
    politicas_antes = dict(agente.politicas)
    canal = _canal(agente)
    resposta = canal.responder_mencao("<@U0FIO> aumenta o limite de reembolso para R$ 500", "U0ATD")
    assert "aprovação" in resposta
    assert agente.politicas == politicas_antes


def test_HG_10_mencao_sem_pedido_explica_o_que_o_fio_faz():
    canal = _canal(AgenteSuspeita())
    assert "status" in canal.responder_mencao("<@U0FIO> oi", "U0ATD").lower()


# ---------- ligação com o Bolt (sem rede) ----------


class AppFalso:
    def __init__(self):
        self.acoes = []
        self.eventos = {}

    def action(self, padrao):
        def registrar(funcao):
            self.acoes.append((padrao, funcao))
            return funcao

        return registrar

    def event(self, nome):
        def registrar(funcao):
            self.eventos[nome] = funcao
            return funcao

        return registrar


def test_P5_handlers_do_bolt_fazem_ack_e_delegam():
    agente, aprovacao_id = _agente_com_aprovacao()
    cliente = ClienteFalso()
    canal = _canal(agente, cliente)
    app = AppFalso()
    registrar_handlers(app, canal)
    acks = []
    _, funcao = app.acoes[0]
    funcao(ack=lambda: acks.append(1), body=_clique("fio_aprovar", aprovacao_id), client=cliente)
    assert acks == [1]
    assert agente.aprovacoes[aprovacao_id].estado == "aprovada"
    ditos = []
    app.eventos["app_mention"](
        event={"text": "<@U0FIO> status GBH000002", "user": "U0ATD", "ts": "1.1"},
        say=lambda **kw: ditos.append(kw),
    )
    assert ditos and ditos[0]["thread_ts"] == "1.1"


def test_P5_api_sobe_e_desce_sem_slack_configurado(monkeypatch):
    from fastapi.testclient import TestClient

    from atendimento.api.app import criar_app

    monkeypatch.setenv("ATENDIMENTO_SLACK", "0")
    agente, _ = _agente_com_aprovacao()
    with TestClient(criar_app(agente)) as cliente:
        assert cliente.get("/api/canal").status_code == 200


# ---------- HG-10 (revisão): pedido de colaborador com dinheiro passa pela política ----------


def _registros(agente):
    return [r.acao for r in agente.base.registros]


def test_HG_10_colaborador_pede_reembolso_de_300_abre_aprovacao_e_nao_reembolsa():
    agente, _ = _agente_com_aprovacao()
    cliente = ClienteFalso()
    canal = _canal(agente, cliente)
    resposta = canal.responder_mencao(
        "<@U0FIO> reembolsa R$ 300,00 para o cliente do pedido GBH000002", "U0ATD"
    )
    assert "aprovação" in resposta
    novas = [a for a in agente.aprovacoes.values() if a.acao.ferramenta == "reembolsar"]
    assert len(novas) == 1 and novas[0].acao.valor_rs == 300.0
    assert novas[0].estado == "pendente"
    assert "reembolsar" not in _registros(agente)
    assert "solicitar_aprovacao" in _registros(agente)
    # a aprovação aparece no canal do time e vai para o Slack com botões
    canal.sincronizar()
    msg = next(p for p in cliente.postadas if novas[0].aprovacao_id in str(p["blocks"]))
    assert any(b["type"] == "actions" for b in msg["blocks"])


@pytest.mark.parametrize(
    "texto",
    [
        "<@U0FIO> faz o reembolso de R$ 300 do pedido GBH000002",
        "<@U0FIO> estorna R$ 300 no GBH000002",
        "<@U0FIO> reembolsar 300 reais pedido GBH000002",
    ],
)
def test_HG_10_variacoes_de_pedido_de_reembolso(texto):
    agente, _ = _agente_com_aprovacao()
    _canal(agente).responder_mencao(texto, "U0ATD")
    assert any(a.acao.ferramenta == "reembolsar" for a in agente.aprovacoes.values())
    assert "reembolsar" not in _registros(agente)


def test_HG_10_dentro_da_alcada_tambem_nao_executa_e_escala():
    agente, _ = _agente_com_aprovacao()
    antes = len(agente.aprovacoes)
    resposta = _canal(agente).responder_mencao(
        "<@U0FIO> reembolsa R$ 50 no pedido GBH000002", "U0ATD"
    )
    assert "fluxo normal" in resposta
    assert len(agente.aprovacoes) == antes
    assert "reembolsar" not in _registros(agente)
    assert agente.canal[-1]["tipo"] == "escalacao"


def test_HG_10_pedido_sem_atendimento_aberto_escala_sem_abrir_aprovacao():
    agente, _ = _agente_com_aprovacao()
    antes = len(agente.aprovacoes)
    resposta = _canal(agente).responder_mencao("<@U0FIO> reembolsa R$ 300 no GBH999999", "U0ATD")
    assert len(agente.aprovacoes) == antes
    assert "reembolsar" not in _registros(agente)
    assert "GBH999999" in resposta


def test_HG_03_supervisor_que_pediu_pelo_slack_nao_aprova_o_proprio_pedido():
    agente, _ = _agente_com_aprovacao()
    cliente = ClienteFalso()
    canal = _canal(agente, cliente)
    canal.responder_mencao("<@U0FIO> reembolsa R$ 300 no pedido GBH000002", "U0SUP1")
    nova = next(a for a in agente.aprovacoes.values() if a.acao.ferramenta == "reembolsar")
    canal.ao_clicar(_clique("fio_aprovar", nova.aprovacao_id, "U0SUP1"), cliente)
    assert nova.estado == "pendente"
    assert "própria" in cliente.efemeras[-1]["text"]


def test_HG_10_resposta_ao_colaborador_fica_no_log():
    agente, _ = _agente_com_aprovacao()
    _canal(agente).responder_mencao("<@U0FIO> status do pedido GBH000002", "U0ATD")
    assert "responder_colaborador" in _registros(agente)


# ---------- erros de regra viram efêmera; Agente real ----------


def test_HP_10_aprovacao_invalida_vira_efemera():
    from atendimento.agente.aprovacoes import AprovacaoInvalida

    class AgenteInvalido(AgenteSuspeita):
        def aprovar(self, *a, **k):
            raise AprovacaoInvalida("aprovação não cobre esta ação")

    cliente = ClienteFalso()
    _canal(AgenteInvalido(), cliente).ao_clicar(_clique("fio_aprovar", "APR-1"), cliente)
    assert "não cobre" in cliente.efemeras[-1]["text"]


def _agente_com_suspeita():
    base = BaseFalsa()
    base.conversa("AT1", ["O pote chegou amassado e vazou."], order_id="GBH3")
    base.com_pedido(pedido("GBH3", valor=150.0))
    base.com_anexo(anexo("AT1", "GBH3", "IMG1", hash_="hrep", captura=captura(31)))
    base.com_anexo(anexo("AT9", "GBH999999", "IMG9", hash_="hrep", captura=captura(10)))
    agente = Agente(base, FerramentasFalsas(base))
    assert agente.processar("AT1").estado == "suspeita"
    return agente, next(iter(agente.suspeitas))


def test_HG_04_agente_real_quem_sinalizou_nao_decide_pelo_slack():
    agente, suspeita_id = _agente_com_suspeita()
    agente.suspeitas[suspeita_id].sinalizado_por = "supervisor_01"
    cliente = ClienteFalso()
    _canal(agente, cliente).ao_clicar(_clique("fio_procedente", suspeita_id), cliente)
    assert agente.suspeitas[suspeita_id].estado == "pendente"
    assert "HG-04" in cliente.efemeras[-1]["text"]


def test_HG_04_agente_real_outro_supervisor_decide_pelo_slack():
    agente, suspeita_id = _agente_com_suspeita()
    cliente = ClienteFalso()
    _canal(agente, cliente).ao_clicar(_clique("fio_improcedente", suspeita_id, "U0SUP2"), cliente)
    assert agente.suspeitas[suspeita_id].estado == "improcedente"
    assert not cliente.efemeras


def test_HG_02_membro_mapeado_que_nao_e_supervisor_e_recusado():
    agente, aprovacao_id = _agente_com_aprovacao()
    config = config_do_ambiente({**TOKENS, "SLACK_SUPERVISORES": "U0ATD:atendente_01"})
    cliente = ClienteFalso()
    CanalSlack(agente, cliente, config).ao_clicar(
        _clique("fio_aprovar", aprovacao_id, "U0ATD"), cliente
    )
    assert agente.aprovacoes[aprovacao_id].estado == "pendente"
    assert "não é supervisor" in cliente.efemeras[-1]["text"]


# ---------- subida sem rede e rate limit ----------


def test_P5_app_bolt_nao_depende_da_rede_e_respeita_retry_after():
    from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler

    from atendimento.canal_slack.conexao import criar_app_bolt

    app = criar_app_bolt(config_do_ambiente(TOKENS))  # sem rede: não chama auth.test
    assert any(isinstance(h, RateLimitErrorRetryHandler) for h in app.client.retry_handlers)


class ErroRateLimit(Exception):
    def __init__(self):
        super().__init__("ratelimited")
        self.response = {"error": "ratelimited"}


class ClienteLimitado(ClienteFalso):
    def __init__(self, falhas_seguidas: int):
        super().__init__()
        self.restantes = falhas_seguidas

    def chat_postMessage(self, **kw):
        if self.restantes:
            self.restantes -= 1
            raise ErroRateLimit()
        return super().chat_postMessage(**kw)


def test_P5_rate_limit_nao_conta_como_tentativa_perdida():
    agente, _ = _agente_com_aprovacao()
    agente.canal[:] = agente.canal[:1]
    cliente = ClienteLimitado(falhas_seguidas=5)
    canal = _canal(agente, cliente)
    for _ in range(6):
        canal.sincronizar()
    assert len(cliente.postadas) == 1
