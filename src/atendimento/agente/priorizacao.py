"""Ordena a fila pelo risco de SLA e pelo custo do canal (HP-01).

SLA de primeira resposta e custo por conversa vêm de `docs/politicas.csv`
(`sla_primeira_resposta.*`, `custo_por_conversa_rs.*`, `horario_atendimento_humano.*`).
Ordem: sem resposta antes de já respondida; depois o vencimento mais cedo (vencidos no topo);
empate: canal mais caro primeiro.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from atendimento.contratos import AGORA, FUSO


def _data(valor: object) -> datetime | None:
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor if valor.tzinfo else valor.replace(tzinfo=FUSO)
    return datetime.fromisoformat(str(valor)).replace(tzinfo=FUSO)


def _hora(texto: str) -> time:
    h, m = texto.split(":")
    return time(int(h), int(m))


def _somar_minutos_comerciais(inicio: datetime, minutos: int, abre: time, fecha: time) -> datetime:
    atual = inicio
    restante = timedelta(minutes=minutos)
    while True:
        abertura = atual.replace(hour=abre.hour, minute=abre.minute, second=0, microsecond=0)
        fechamento = atual.replace(hour=fecha.hour, minute=fecha.minute, second=0, microsecond=0)
        if atual < abertura:
            atual = abertura
        if atual >= fechamento:
            atual = abertura + timedelta(days=1)
            continue
        disponivel = fechamento - atual
        if restante <= disponivel:
            return atual + restante
        restante -= disponivel
        atual = abertura + timedelta(days=1)


def vencimento_sla(conversa: dict, politicas: dict[str, str]) -> datetime:
    canal = conversa["canal"]
    abertura = _data(conversa["data_abertura"])
    if canal == "whatsapp":
        minutos = int(politicas["sla_primeira_resposta.whatsapp.minutos"])
        if politicas.get("sla_primeira_resposta.whatsapp.conta_apenas_horario_comercial") == "True":
            return _somar_minutos_comerciais(
                abertura,
                minutos,
                _hora(politicas["horario_atendimento_humano.inicio"]),
                _hora(politicas["horario_atendimento_humano.fim"]),
            )
        return abertura + timedelta(minutes=minutos)
    horas = float(politicas[f"sla_primeira_resposta.{canal}.horas"])
    return abertura + timedelta(hours=horas)


def priorizar(fila: list[dict], politicas: dict[str, str], agora: datetime = AGORA) -> list[dict]:
    enriquecida = []
    for conversa in fila:
        venc = vencimento_sla(conversa, politicas)
        enriquecida.append(
            {
                **conversa,
                "vencimento_sla": venc,
                "sla_vencido": venc < agora,
                "respondida": _data(conversa.get("data_primeira_resposta")) is not None,
                "custo_canal_rs": float(politicas[f"custo_por_conversa_rs.{conversa['canal']}"]),
            }
        )
    enriquecida.sort(key=lambda c: (c["respondida"], c["vencimento_sla"], -c["custo_canal_rs"]))
    for posicao, conversa in enumerate(enriquecida, start=1):
        conversa["prioridade"] = posicao
    return enriquecida
