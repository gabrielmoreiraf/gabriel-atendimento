"""Reexecução do motor de políticas e do verificador sobre o histórico (HG-18).

Funções puras: recebem linhas já lidas (dicts dos CSVs) e objetos de `contratos.py`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from atendimento.avaliacao.historico import data_hora
from atendimento.contratos import (
    AcaoAnterior,
    AcaoProposta,
    Anexo,
    Decisao,
    Papel,
    Pedido,
    Resultado,
    VeredictoEvidencia,
)
from atendimento.politicas import decidir
from atendimento.politicas.motor import LIMITE_POR_FERRAMENTA
from atendimento.verificacao import verificar

FERRAMENTAS_COM_DINHEIRO = tuple(LIMITE_POR_FERRAMENTA)


@dataclass(frozen=True)
class LinhaAcao:
    acao_id: str
    conversation_id: str
    order_id: str
    data_hora: datetime
    acao: str
    valor_rs: float
    aprovado_por: str | None
    categoria: str | None
    decisao: Decisao
    divergencia: str | None  # None = o agente teria feito o mesmo que o time


@dataclass(frozen=True)
class LinhaAnexo:
    conversation_id: str
    order_id: str
    veredicto: VeredictoEvidencia
    acoes_com_dinheiro: tuple[str, ...]
    custo_evitado_rs: float  # valor do pedido × 45% se suspeita e houve ação com dinheiro


def mapa_tag_categoria(politicas: dict[str, str]) -> dict[str, str]:
    """`tag_agente` do histórico -> categoria de `politicas.csv` (primeira com a tag)."""
    mapa: dict[str, str] = {}
    sufixo = ".tag_equivalente"
    for chave, valor in politicas.items():
        if chave.startswith("categorias.") and chave.endswith(sufixo) and valor:
            mapa.setdefault(valor, chave[len("categorias.") : -len(sufixo)])
    return mapa


def _papel(colaborador_id: str, equipe: list[dict]) -> Papel:
    for pessoa in equipe:
        if pessoa["colaborador_id"] == colaborador_id:
            return Papel(pessoa["cargo"])
    return Papel.ATENDENTE


def _com_dinheiro(acoes: list[dict]) -> list[dict]:
    return sorted(
        (a for a in acoes if a["acao"] in FERRAMENTAS_COM_DINHEIRO and a["valor_rs"]),
        key=lambda a: (a["data_hora"], a["acao_id"]),
    )


def _divergencia(
    decisao: Decisao,
    valor: float,
    pedido: Pedido | None,
    agora: datetime,
    politicas: dict[str, str],
) -> str | None:
    if decisao.resultado is Resultado.EXECUTAR:
        return None
    if decisao.resultado is Resultado.PEDIR_APROVACAO:
        return "alcada" if valor > float(politicas[decisao.regra]) else "alcada_acumulada"
    if decisao.regra.endswith(".prazo_dias_corridos_do_recebimento"):
        entrega = pedido.data_entrega if pedido else None
        if entrega is None or entrega > agora.date():
            return "antes_do_recebimento"  # a janela nem começou: Q12, não prazo vencido
        return "prazo"
    if decisao.regra.endswith(".max_trocas_por_pedido"):
        return "troca_repetida"
    if decisao.regra.endswith(".acoes_permitidas"):
        return "acao_nao_permitida"
    if decisao.resultado is Resultado.ESCALAR and pedido is None:
        return "sem_pedido"
    if decisao.resultado is Resultado.ESCALAR:
        return "caso_sensivel"
    if decisao.resultado is Resultado.BLOQUEAR:
        return "autoaprovacao"
    return "outro"


def avaliar_acoes(
    acoes: list[dict],
    *,
    pedidos: dict[str, Pedido],
    conversas: dict[str, dict],
    politicas: dict[str, str],
    equipe: list[dict],
) -> list[LinhaAcao]:
    """Para cada ação com dinheiro, em ordem cronológica, o que o motor teria decidido.

    "Agora" de cada decisão = `data_hora` da ação. As ações anteriores do pedido são as que o
    time de fato executou antes (o histórico como aconteceu), com a aprovação registrada.
    """
    tags = mapa_tag_categoria(politicas)
    anteriores: dict[str, list[AcaoAnterior]] = defaultdict(list)
    linhas = []
    for a in _com_dinheiro(acoes):
        valor = float(a["valor_rs"])
        aprovado_por = a["aprovado_por"] or None
        conversa = conversas.get(a["conversation_id"], {})
        categoria = tags.get(conversa.get("tag_agente", ""))
        agora = data_hora(a["data_hora"])
        pedido = pedidos.get(a["order_id"])
        decisao = decidir(
            AcaoProposta(
                ferramenta=a["acao"],
                papel=_papel(a["executado_por"], equipe),
                executado_por=a["executado_por"],
                conversation_id=a["conversation_id"],
                order_id=a["order_id"],
                valor_rs=valor,
                categoria=categoria,
                aprovacao_id=a["acao_id"] if aprovado_por else None,
                aprovado_por=aprovado_por,
            ),
            pedido=pedido,
            acoes_anteriores=list(anteriores[a["order_id"]]),
            politicas=politicas,
            equipe=equipe,
            agora=agora,
        )
        linhas.append(
            LinhaAcao(
                acao_id=a["acao_id"],
                conversation_id=a["conversation_id"],
                order_id=a["order_id"],
                data_hora=agora,
                acao=a["acao"],
                valor_rs=valor,
                aprovado_por=aprovado_por,
                categoria=categoria,
                decisao=decisao,
                divergencia=_divergencia(decisao, valor, pedido, agora, politicas),
            )
        )
        anteriores[a["order_id"]].append(
            AcaoAnterior(
                acao_id=a["acao_id"],
                order_id=a["order_id"],
                acao=a["acao"],
                valor_rs=valor,
                executado_por=a["executado_por"],
                aprovado_por=aprovado_por,
            )
        )
    return linhas


def casos_m11(acoes: list[dict], politicas: dict[str, str]) -> list[tuple[str, str]]:
    """M11 (`ingestao/baseline_metricas.md`): (pedido, ação) repetida em 2+ conversas, cada
    execução dentro do limite do atendente, nenhuma aprovada, e a soma acima do limite."""
    grupos: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for a in _com_dinheiro(acoes):
        grupos[(a["order_id"], a["acao"])].append(a)
    casos = []
    for (order_id, acao), lista in grupos.items():
        limite = float(politicas[LIMITE_POR_FERRAMENTA[acao]])
        valores = [float(x["valor_rs"]) for x in lista]
        if (
            len({x["conversation_id"] for x in lista}) >= 2
            and not any(x["aprovado_por"] for x in lista)
            and all(v <= limite for v in valores)
            and round(sum(valores), 2) > limite
        ):
            casos.append((order_id, acao))
    return sorted(casos)


def avaliar_anexos(
    anexos: list[Anexo],
    *,
    pedidos: dict[str, Pedido],
    conversas: dict[str, dict],
    acoes: list[dict],
    trocas_reenvios: list[dict],
    enviado_em: dict[str, datetime] | None = None,
) -> list[LinhaAnexo]:
    """Roda o verificador em cada conversa com anexo e cruza com as ações com dinheiro dela.

    Só entra o que existia quando a foto chegou: anexos com o mesmo hash enviados antes e
    reenvios do cliente solicitados antes da abertura da conversa.
    """
    enviado_em = enviado_em or {}
    por_hash: dict[str, list[Anexo]] = defaultdict(list)
    por_conversa: dict[str, list[Anexo]] = defaultdict(list)
    for anexo in anexos:
        por_conversa[anexo.conversation_id].append(anexo)
        if anexo.hash_perceptual:
            por_hash[anexo.hash_perceptual].append(anexo)
    dinheiro: dict[str, list[str]] = defaultdict(list)
    for a in _com_dinheiro(acoes):
        dinheiro[a["conversation_id"]].append(a["acao"])

    linhas = []
    for conversation_id, lista in sorted(por_conversa.items()):
        conversa = conversas.get(conversation_id, {})
        order_id = conversa.get("order_id") or next((x.order_id for x in lista if x.order_id), None)
        pedido = pedidos.get(order_id or "")
        if pedido is None:
            continue
        mesmo_hash = {}
        for anexo in lista:
            if not anexo.hash_perceptual:
                continue
            limite = enviado_em.get(anexo.anexo_id)
            mesmo_hash[anexo.hash_perceptual] = [
                x
                for x in por_hash[anexo.hash_perceptual]
                if limite is None
                or x.anexo_id == anexo.anexo_id
                or (enviado_em.get(x.anexo_id) and enviado_em[x.anexo_id] < limite)
            ]
        abertura = conversa.get("data_abertura", "")
        reenvios = sum(
            1
            for t in trocas_reenvios
            if t["customer_id"] == pedido.customer_id
            and t.get("tipo") == "reenvio"  # EC-19: limiar do verificador conta só reenvios
            and (not abertura or t["data_solicitacao"] < abertura)
        )
        veredicto = verificar(
            pedido=pedido,
            anexos=lista,
            anexos_mesmo_hash=mesmo_hash,
            reenvios_anteriores_cliente=reenvios,
        )
        acoes_conv = tuple(dinheiro.get(conversation_id, ()))
        custo = veredicto.custo_aceitar_falso_rs if veredicto.suspeita and acoes_conv else 0.0
        linhas.append(
            LinhaAnexo(
                conversation_id=conversation_id,
                order_id=pedido.order_id,
                veredicto=veredicto,
                acoes_com_dinheiro=acoes_conv,
                custo_evitado_rs=custo,
            )
        )
    return linhas
