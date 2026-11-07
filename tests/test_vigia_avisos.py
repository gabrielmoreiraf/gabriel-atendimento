"""Colega que avisa o time sem ser perguntado (P1, HG-20, HG-21, Q9)."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import pytest

from atendimento.contratos import AGORA, FUSO
from atendimento.vigia import (
    JANELA_AVISO_SLA_MIN,
    LEMBRETE_APROVACAO_HORAS,
    alertas_sla,
    lembretes_aprovacao,
    prazo_primeira_resposta,
)

POLITICAS = {
    "horario_atendimento_humano.inicio": "08:00",
    "horario_atendimento_humano.fim": "20:00",
    "sla_primeira_resposta.whatsapp.minutos": "30",
    "sla_primeira_resposta.whatsapp.conta_apenas_horario_comercial": "True",
    "sla_primeira_resposta.email.horas": "24",
    "sla_primeira_resposta.reclame_aqui.horas": "48",
    "reclamacao_suspeita.prazo_decisao_horas": "24",
}
EQUIPE = [
    {
        "colaborador_id": "supervisor_01",
        "cargo": "supervisor",
        "turno": "08h-20h",
        "status": "ativo",
    },
    {
        "colaborador_id": "supervisor_02",
        "cargo": "supervisor",
        "turno": "08h-17h",
        "status": "ativo",
    },
    {
        "colaborador_id": "supervisor_03",
        "cargo": "supervisor",
        "turno": "08h-17h",
        "status": "ativo",
    },
]


def _hora(dia: int, h: int, m: int = 0) -> datetime:
    return datetime(2026, 11, dia, h, m, tzinfo=FUSO)


def _conversa(cid, canal, abertura, primeira_resposta="", atendente="atendente_01"):
    return {
        "conversation_id": cid,
        "canal": canal,
        "data_abertura": abertura,
        "data_primeira_resposta": primeira_resposta,
        "atendente_id": atendente,
        "customer_id": "CH1",
    }


# ---------- prazo do SLA ----------


def test_HG_20_whatsapp_aberto_de_madrugada_vence_as_8h30():
    prazo = prazo_primeira_resposta(_conversa("A", "whatsapp", "2026-11-02 03:10:00"), POLITICAS)
    assert prazo == _hora(2, 8, 30)


def test_HG_20_whatsapp_aberto_19h50_vence_8h20_do_dia_seguinte():
    prazo = prazo_primeira_resposta(_conversa("A", "whatsapp", "2026-11-01 19:50:00"), POLITICAS)
    assert prazo == _hora(2, 8, 20)


def test_HG_20_email_e_reclame_aqui_contam_horas_corridas():
    assert prazo_primeira_resposta(
        _conversa("A", "email", "2026-11-01 07:00:00"), POLITICAS
    ) == _hora(2, 7)
    assert prazo_primeira_resposta(
        _conversa("A", "reclame_aqui", "2026-10-31 09:00:00"), POLITICAS
    ) == _hora(2, 9)


# ---------- alertas ----------


def test_HG_20_janela_de_aviso_vem_do_Q9():
    assert JANELA_AVISO_SLA_MIN == 10


def test_HG_20_avisa_quem_vai_estourar_dentro_da_janela_e_quem_ja_estourou():
    fila = [
        _conversa("WA_JANELA", "whatsapp", "2026-11-02 03:00:00"),  # vence 08:30
        _conversa("WA_RESPONDIDA", "whatsapp", "2026-11-02 03:00:00", "2026-11-02 08:05:00"),
        _conversa("EMAIL_VENCIDO", "email", "2026-11-01 07:00:00"),  # venceu 07:00
        _conversa("EMAIL_LONGE", "email", "2026-11-01 20:00:00"),  # vence amanhã... 02/11 20:00
    ]
    alertas = alertas_sla(fila, POLITICAS, _hora(2, 8, 20))
    por_id = {a.conversation_id: a for a in alertas}
    assert set(por_id) == {"WA_JANELA", "EMAIL_VENCIDO"}
    assert por_id["WA_JANELA"].situacao == "vai_estourar"
    assert por_id["WA_JANELA"].minutos_restantes == pytest.approx(10)
    assert por_id["WA_JANELA"].prazo == _hora(2, 8, 30)
    assert por_id["EMAIL_VENCIDO"].situacao == "estourado"
    assert por_id["EMAIL_VENCIDO"].minutos_restantes == pytest.approx(-80)
    assert por_id["WA_JANELA"].para == "atendente_01"


def test_HG_20_fora_da_janela_nao_avisa():
    fila = [_conversa("WA", "whatsapp", "2026-11-02 03:00:00")]
    assert alertas_sla(fila, POLITICAS, _hora(2, 8, 0)) == []


def test_HG_20_aviso_diz_o_que_aconteceu_impacto_e_quem_age_sem_dado_pessoal():
    fila = [_conversa("WA", "whatsapp", "2026-11-02 03:00:00")]
    (alerta,) = alertas_sla(fila, POLITICAS, _hora(2, 8, 25))
    assert "WA" in alerta.texto and "08:30" in alerta.texto
    assert "SLA" in alerta.texto
    assert "CH1" not in alerta.texto


@pytest.mark.integracao
def test_HG_20_fila_real_bate_com_m5():
    raiz = Path(__file__).resolve().parents[1] / "docs"
    with open(raiz / "fila_aberta.csv", encoding="utf-8", newline="") as f:
        fila = list(csv.DictReader(f))
    with open(raiz / "politicas.csv", encoding="utf-8", newline="") as f:
        politicas = {f"{x['secao']}.{x['regra']}": x["valor"] for x in csv.DictReader(f)}
    # 08:00: o e-mail já fora do SLA (M5: 1) e o WhatsApp AT116664, aberto 01/11 19:38:52,
    # que usou 21 min no dia anterior e vence às 08:08:52 (9 min, dentro da janela)
    as_8h = alertas_sla(fila, politicas, AGORA)
    assert [(a.canal, a.situacao) for a in as_8h] == [
        ("email", "estourado"),
        ("whatsapp", "vai_estourar"),
    ]
    assert as_8h[1].conversation_id == "AT116664"
    # 08:20: as 18 conversas de WhatsApp sem 1ª resposta (M5) aparecem: 16 abertas fora do
    # horário vencem às 08:30; AT116666 (aberta 19:56:45) vence às 08:26:45; AT116664 já venceu
    as_8h20 = alertas_sla(fila, politicas, _hora(2, 8, 20))
    whatsapp = {a.conversation_id: a for a in as_8h20 if a.canal == "whatsapp"}
    assert len(whatsapp) == 18
    assert sum(a.prazo == _hora(2, 8, 30) for a in whatsapp.values()) == 16
    assert whatsapp["AT116664"].situacao == "estourado"
    assert whatsapp["AT116666"].prazo == datetime(2026, 11, 2, 8, 26, 45, tzinfo=FUSO)


# ---------- lembretes de aprovação ----------


def _pendente(aid, solicitado_em, solicitado_por="agente", executado_por="agente"):
    acao = {"ferramenta": "reembolsar", "executado_por": executado_por, "order_id": "P1"}
    return {
        "aprovacao_id": aid,
        "acao": json.dumps(acao),
        "solicitado_por": solicitado_por,
        "estado": "pendente",
        "solicitado_em": solicitado_em,
    }


def test_HG_21_lembrete_so_depois_de_2_horas():
    assert LEMBRETE_APROVACAO_HORAS == 2
    pendentes = [_pendente("APR1", "2026-11-02 08:00:00"), _pendente("APR2", "2026-11-02 09:59:00")]
    lembretes = lembretes_aprovacao(pendentes, _hora(2, 11, 0), equipe=EQUIPE, politicas=POLITICAS)
    assert [lembrete.aprovacao_id for lembrete in lembretes] == ["APR1"]
    assert lembretes[0].nivel == 1
    assert lembretes[0].para in {"supervisor_01", "supervisor_02", "supervisor_03"}
    assert lembretes[0].prazo == _hora(3, 8)  # 24 h da política de suspeita
    assert lembretes[0].texto.count("APR1") >= 1


def test_HG_21_sem_resposta_de_novo_chama_outro_supervisor_que_nao_e_o_autor():
    pendentes = [
        _pendente(
            "APR1",
            "2026-11-02 08:00:00",
            solicitado_por="supervisor_02",
            executado_por="supervisor_02",
        )
    ]
    primeiro = lembretes_aprovacao(pendentes, _hora(2, 10, 30), equipe=EQUIPE, politicas=POLITICAS)
    segundo = lembretes_aprovacao(pendentes, _hora(2, 12, 30), equipe=EQUIPE, politicas=POLITICAS)
    assert primeiro[0].nivel == 1 and segundo[0].nivel == 2
    assert "supervisor_02" not in {primeiro[0].para, segundo[0].para}
    assert segundo[0].para != primeiro[0].para


def test_HG_21_das_17h_as_20h_so_supervisor_01_e_depois_fila_para_8h():
    pendentes = [_pendente("APR1", "2026-11-02 14:00:00")]
    as_18h = lembretes_aprovacao(pendentes, _hora(2, 18, 0), equipe=EQUIPE, politicas=POLITICAS)
    assert as_18h[0].para == "supervisor_01"
    as_21h = lembretes_aprovacao(pendentes, _hora(2, 21, 0), equipe=EQUIPE, politicas=POLITICAS)
    assert as_21h[0].para is None
    assert "08:00" in as_21h[0].texto


def test_HG_21_lembrete_avisa_quando_passou_das_24_horas():
    pendentes = [_pendente("APR1", "2026-11-01 08:00:00")]
    (lembrete,) = lembretes_aprovacao(pendentes, _hora(2, 9, 0), equipe=EQUIPE, politicas=POLITICAS)
    assert lembrete.vencido is True
    assert "prazo" in lembrete.texto.lower()


def test_HG_21_aprovacao_decidida_nao_gera_lembrete():
    decidida = {**_pendente("APR1", "2026-11-02 05:00:00"), "estado": "aprovada"}
    assert lembretes_aprovacao([decidida], _hora(2, 11), equipe=EQUIPE, politicas=POLITICAS) == []


def test_HG_21_lembrete_traz_mensagem_neutra_ao_cliente_da_conversa():
    acao = {"ferramenta": "reembolsar", "executado_por": "agente", "conversation_id": "AT9"}
    pendente = {**_pendente("APR1", "2026-11-02 08:00:00"), "acao": json.dumps(acao)}
    (lembrete,) = lembretes_aprovacao(
        [pendente], _hora(2, 10, 30), equipe=EQUIPE, politicas=POLITICAS
    )
    assert lembrete.conversation_id == "AT9"
    texto = lembrete.mensagem_cliente.lower()
    assert "segue em análise" in texto
    for promessa in ("aprovad", "estorno", "reembols", "garant"):
        assert promessa not in texto
