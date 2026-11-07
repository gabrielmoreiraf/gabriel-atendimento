"""Detecção de padrões de causa comum (HG-17). Só leitura da base.

As contagens seguem as mesmas regras de `ingestao/baseline_metricas.py` (M4, M7), para
bater com `ingestao/baseline_metricas.md`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from atendimento.contratos import AGORA
from atendimento.dados.repositorio import Base

COBRADAS = ("capturada", "paga")


@dataclass(frozen=True)
class Padrao:
    tipo: str  # cobranca_em_dobro, contato_repetido
    fator: str  # o que os casos têm em comum, em texto neutro
    escopo: tuple[str, ...]  # order_ids afetados
    evidencia: dict[str, object]  # consulta de origem e contagens
    clientes: dict[str, str] = field(default_factory=dict)  # order_id -> customer_id
    conversation_ids: tuple[str, ...] = ()


def _linhas(base: Base, sql: str) -> list[dict]:
    return [dict(linha) for linha in base.conexao.execute(sql).fetchall()]


def cobranca_em_dobro(base: Base) -> Padrao:
    """M7: pedidos com 2+ transações capturadas/pagas em `pagamentos_gateway` (ainda sem estorno)."""
    cobradas: dict[str, int] = defaultdict(int)
    clientes: dict[str, str] = {}
    for t in _linhas(base, "SELECT order_id, customer_id, status FROM pagamentos_gateway"):
        if t["status"] in COBRADAS:
            cobradas[t["order_id"]] += 1
            clientes.setdefault(t["order_id"], t["customer_id"])
    escopo = tuple(sorted(o for o, n in cobradas.items() if n > 1))
    return Padrao(
        tipo="cobranca_em_dobro",
        fator="gateway de pagamentos: mesma compra cobrada mais de uma vez",
        escopo=escopo,
        evidencia={
            "consulta": "pagamentos_gateway.csv agrupado por order_id; pedidos com 2+ "
            "transações com status capturada ou paga (M7)",
            "contagem": len(escopo),
        },
        clientes={o: clientes[o] for o in escopo},
    )


def contato_repetido(base: Base) -> Padrao:
    """M4: pares cliente+pedido com 2+ conversas em `historico_conversas`."""
    conversas: dict[tuple[str, str], list[str]] = defaultdict(list)
    for c in _linhas(
        base, "SELECT conversation_id, customer_id, order_id FROM historico_conversas"
    ):
        if c["order_id"]:
            conversas[(c["customer_id"], c["order_id"])].append(c["conversation_id"])
    repetidos = {par: ids for par, ids in conversas.items() if len(ids) > 1}
    return Padrao(
        tipo="contato_repetido",
        fator="o mesmo cliente voltou a falar do mesmo pedido em outra conversa",
        escopo=tuple(sorted({order_id for _, order_id in repetidos})),
        evidencia={
            "consulta": "historico_conversas.csv agrupado por (customer_id, order_id) com "
            "order_id preenchido; pares com 2+ conversas (M4)",
            "contagem": len(repetidos),
            "conversas": sum(len(ids) for ids in repetidos.values()),
        },
        clientes={order_id: customer_id for customer_id, order_id in repetidos},
        conversation_ids=tuple(sorted(c for ids in repetidos.values() for c in ids)),
    )


def detectar_padroes(base: Base, agora: datetime = AGORA) -> list[Padrao]:
    """Padrões de causa comum com escopo e evidência. `agora` fica no contrato; as regras
    atuais olham a base inteira, que já representa a empresa em `AGORA`."""
    del agora
    return [p for p in (cobranca_em_dobro(base), contato_repetido(base)) if p.escopo]
