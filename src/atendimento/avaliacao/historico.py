"""Leitura do histórico em `docs/` com o módulo `csv` (UTF-8, somente leitura).

Monta os objetos de `contratos.py` que o motor de políticas e o verificador recebem.
Os CSVs da base usam separador "," (conferido no cabeçalho de cada arquivo usado aqui).
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from atendimento.contratos import FUSO, Anexo, Item, Pedido


@dataclass
class Historico:
    politicas: dict[str, str]
    equipe: list[dict]
    pedidos: dict[str, Pedido]
    conversas: dict[str, dict]
    acoes: list[dict]
    anexos: list[Anexo]
    anexo_enviado_em: dict[str, datetime] = field(default_factory=dict)
    trocas_reenvios: list[dict] = field(default_factory=list)
    mensagens_do_cliente: dict[str, list[str]] = field(default_factory=dict)


def ler_csv(caminho: Path) -> list[dict]:
    with open(caminho, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=","))


def data_hora(valor: str | None) -> datetime | None:
    if not valor:
        return None
    return datetime.fromisoformat(valor).replace(tzinfo=FUSO)


def _data(valor: str | None) -> date | None:
    return date.fromisoformat(valor[:10]) if valor else None


def _texto(valor: str | None) -> str | None:
    return valor or None


def carregar_historico(pasta: Path) -> Historico:
    pasta = Path(pasta)
    politicas = {f"{x['secao']}.{x['regra']}": x["valor"] for x in ler_csv(pasta / "politicas.csv")}
    itens: dict[str, list[Item]] = defaultdict(list)
    for i in sorted(ler_csv(pasta / "itens_pedido.csv"), key=lambda i: int(i["linha"])):
        itens[i["order_id"]].append(
            Item(
                item_id=i["item_id"],
                sku=i["sku"],
                descricao=i["descricao"],
                tipo_item=i["tipo_item"],
                valor_total=float(i["valor_total"] or 0),
                texto_personalizacao=_texto(i["texto_personalizacao"]),
            )
        )
    pedidos = {
        p["order_id"]: Pedido(
            order_id=p["order_id"],
            customer_id=p["customer_id"],
            marca=p["marca"],
            valor=float(p["valor"] or 0),
            status_entrega=p["status_entrega"],
            data_separacao=_data(p["data_separacao"]),
            data_entrega=_data(p["data_entrega"]),
            lote_produto=_texto(p["lote_produto"]),
            itens=tuple(itens.get(p["order_id"], ())),
        )
        for p in ler_csv(pasta / "pedidos.csv")
    }
    linhas_anexos = ler_csv(pasta / "anexos_conversas.csv")
    anexos = [
        Anexo(
            anexo_id=a["anexo_id"],
            conversation_id=a["conversation_id"],
            order_id=_texto(a["order_id"]),
            hash_perceptual=_texto(a["hash_perceptual"]),
            exif_data_captura=data_hora(a["exif_data_captura"]),
            exif_software=_texto(a["exif_software"]),
            descricao_visual=a["descricao_visual"],
        )
        for a in linhas_anexos
    ]
    return Historico(
        politicas=politicas,
        equipe=ler_csv(pasta / "equipe_atendimento.csv"),
        pedidos=pedidos,
        conversas={c["conversation_id"]: c for c in ler_csv(pasta / "historico_conversas.csv")},
        acoes=ler_csv(pasta / "acoes_executadas_sistemas.csv"),
        anexos=anexos,
        anexo_enviado_em={
            a["anexo_id"]: data_hora(a["enviado_em"]) for a in linhas_anexos if a.get("enviado_em")
        },
        trocas_reenvios=ler_csv(pasta / "trocas_reenvios.csv"),
        mensagens_do_cliente=_mensagens_do_cliente(pasta / "historico_mensagens.csv"),
    )


def _mensagens_do_cliente(caminho: Path) -> dict[str, list[str]]:
    """Textos com autor = cliente, por conversa, em ordem de `timestamp`, `message_id`."""
    if not caminho.exists():
        return {}
    por_conversa: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for m in ler_csv(caminho):
        if m["autor"] == "cliente":
            por_conversa[m["conversation_id"]].append((m["timestamp"], m["message_id"], m["texto"]))
    return {cid: [t for *_, t in sorted(lista)] for cid, lista in por_conversa.items()}
