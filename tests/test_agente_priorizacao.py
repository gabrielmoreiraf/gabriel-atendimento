"""Priorização da fila por risco de SLA e custo do canal (HP-01)."""

from datetime import datetime

from atendimento.agente.priorizacao import priorizar, vencimento_sla
from atendimento.contratos import AGORA, FUSO

# Linhas de docs/politicas.csv (sla_primeira_resposta, custo_por_conversa_rs, horário humano)
POLITICAS = {
    "horario_atendimento_humano.inicio": "08:00",
    "horario_atendimento_humano.fim": "20:00",
    "sla_primeira_resposta.whatsapp.minutos": "30",
    "sla_primeira_resposta.whatsapp.conta_apenas_horario_comercial": "True",
    "sla_primeira_resposta.email.horas": "24",
    "sla_primeira_resposta.reclame_aqui.horas": "48",
    "custo_por_conversa_rs.whatsapp": "4.8",
    "custo_por_conversa_rs.email": "7.2",
    "custo_por_conversa_rs.reclame_aqui": "42.0",
}


def _conversa(cid, canal, abertura, primeira_resposta=""):
    return {
        "conversation_id": cid,
        "canal": canal,
        "data_abertura": abertura,
        "data_primeira_resposta": primeira_resposta,
    }


def test_HP_01_whatsapp_aberto_a_noite_vence_as_0830():
    venc = vencimento_sla(_conversa("A", "whatsapp", "2026-11-01 21:41:29"), POLITICAS)
    assert venc == datetime(2026, 11, 2, 8, 30, tzinfo=FUSO)


def test_HP_01_whatsapp_aberto_19h50_conta_so_horario_comercial():
    venc = vencimento_sla(_conversa("A", "whatsapp", "2026-11-01 19:50:00"), POLITICAS)
    assert venc == datetime(2026, 11, 2, 8, 20, tzinfo=FUSO)


def test_HP_01_reclame_aqui_vence_48h_apos_abertura():
    venc = vencimento_sla(_conversa("A", "reclame_aqui", "2026-10-31 15:11:54"), POLITICAS)
    assert venc == datetime(2026, 11, 2, 15, 11, 54, tzinfo=FUSO)


def test_HP_01_email_vence_24h_apos_abertura():
    venc = vencimento_sla(_conversa("A", "email", "2026-11-01 14:05:28"), POLITICAS)
    assert venc == datetime(2026, 11, 2, 14, 5, 28, tzinfo=FUSO)


def test_HP_01_fila_ordenada_por_vencimento_e_numerada():
    fila = [
        _conversa("RA", "reclame_aqui", "2026-11-01 10:00:00"),  # vence 03/11 10h
        _conversa("WA", "whatsapp", "2026-11-01 22:00:00"),  # vence 02/11 08h30
        _conversa("EM_VENCIDO", "email", "2026-10-31 15:58:30"),  # venceu 01/11
        _conversa("EM", "email", "2026-11-01 20:00:00"),  # vence 02/11 20h
    ]
    ordenada = priorizar(fila, POLITICAS, agora=AGORA)
    assert [c["conversation_id"] for c in ordenada] == ["EM_VENCIDO", "WA", "EM", "RA"]
    assert [c["prioridade"] for c in ordenada] == [1, 2, 3, 4]
    assert ordenada[0]["sla_vencido"] is True
    assert ordenada[1]["sla_vencido"] is False


def test_HP_01_ja_respondida_vai_para_depois_das_sem_resposta():
    fila = [
        _conversa("RESP", "whatsapp", "2026-11-01 19:12:25", "2026-11-01 19:21:05"),
        _conversa("RA", "reclame_aqui", "2026-11-01 10:00:00"),
    ]
    ordenada = priorizar(fila, POLITICAS, agora=AGORA)
    assert [c["conversation_id"] for c in ordenada] == ["RA", "RESP"]


def test_HP_01_mesmo_vencimento_canal_mais_caro_primeiro():
    fila = [
        _conversa("EM", "email", "2026-11-01 08:00:00"),
        _conversa("RA", "reclame_aqui", "2026-10-31 08:00:00"),
    ]
    ordenada = priorizar(fila, POLITICAS, agora=AGORA)
    assert ordenada[0]["conversation_id"] == "RA"
    assert ordenada[0]["custo_canal_rs"] == 42.0
