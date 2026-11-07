"""Rotas do vigia (P1, HG-20, HG-21): o colega que avisa o time sem ser perguntado.

Plugar no app: `app.include_router(criar_router(ag))`, em que `ag()` devolve o `Agente` do
W4 (usa `base`, `casos`, `postar_no_canal` e `emitir`). Conversas que o agente já tratou
(`casos`) não geram aviso de SLA. Cada aviso é postado uma vez só por processo.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import asdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder

from atendimento.contratos import AGORA, FUSO, AcaoProposta, Papel
from atendimento.ferramentas import mascarar_texto
from atendimento.vigia import alertas_sla, lembretes_aprovacao


def _agora(valor: str | None) -> datetime:
    if not valor:
        return AGORA
    try:
        momento = datetime.fromisoformat(valor)
    except ValueError as erro:
        raise HTTPException(422, f"agora inválido: {valor!r} (use ISO 8601)") from erro
    return momento if momento.tzinfo else momento.replace(tzinfo=FUSO)


def _serializar(aviso: Any) -> dict:
    corpo = jsonable_encoder({**asdict(aviso), "chave": aviso.chave})
    corpo["texto"] = mascarar_texto(corpo["texto"])
    return corpo


def criar_router(obter_contexto: Callable[[], Any]) -> APIRouter:
    router = APIRouter(prefix="/api/vigia", tags=["vigia"])
    postados: set[str] = set()
    trava_local = threading.RLock()

    def contexto() -> Any:
        return obter_contexto()

    def coletar(ctx: Any, agora: datetime) -> tuple[list, list]:
        base = ctx.base
        with getattr(base, "trava", None) or nullcontext():
            fila = base.fila()
            politicas = base.politicas()
            equipe = base.equipe()
            pendentes = [
                dict(linha)
                for linha in base.conexao.execute(
                    "SELECT * FROM aprovacoes WHERE estado = 'pendente' ORDER BY aprovacao_id"
                ).fetchall()
            ]
        tratadas = set(getattr(ctx, "casos", {}) or {})
        fila = [c for c in fila if c["conversation_id"] not in tratadas]
        return (
            alertas_sla(fila, politicas, agora),
            lembretes_aprovacao(pendentes, agora, equipe=equipe, politicas=politicas),
        )

    @router.get("/alertas")
    def alertas(agora: str | None = None, ctx: Any = Depends(contexto)) -> dict:  # noqa: B008
        momento = _agora(agora)
        sla, aprovacoes = coletar(ctx, momento)
        return {
            "agora": momento.isoformat(),
            "sla": [_serializar(a) for a in sla],
            "aprovacoes": [_serializar(lembrete) for lembrete in aprovacoes],
        }

    @router.post("/rodar")
    def rodar(agora: str | None = None, ctx: Any = Depends(contexto)) -> dict:  # noqa: B008
        momento = _agora(agora)
        sla, aprovacoes = coletar(ctx, momento)
        novos = []
        with trava_local:
            for aviso in sla:
                if aviso.chave in postados:
                    continue
                postados.add(aviso.chave)
                ctx.postar_no_canal(
                    "aviso", aviso.para, aviso.texto, aviso.conversation_id, chave=aviso.chave
                )
                novos.append(aviso)
            for lembrete in aprovacoes:
                if lembrete.chave in postados:
                    continue
                postados.add(lembrete.chave)
                cid = lembrete.conversation_id or _conversa_da_aprovacao(ctx, lembrete.aprovacao_id)
                _avisar_cliente(ctx, cid, lembrete.mensagem_cliente)
                ctx.postar_no_canal(
                    "aprovacao",
                    lembrete.para,
                    lembrete.texto,
                    cid,
                    chave=lembrete.chave,
                    aprovacao_id=lembrete.aprovacao_id,
                )
                novos.append(lembrete)
        ja_postados = len(sla) + len(aprovacoes) - len(novos)
        if novos and hasattr(ctx, "emitir"):
            ctx.emitir(
                "vigia",
                {"agora": momento.isoformat(), "novos": len(novos), "ja_postados": ja_postados},
            )
        return {
            "agora": momento.isoformat(),
            "postados": [_serializar(a) for a in novos],
            "ja_postados": ja_postados,
        }

    return router


def _avisar_cliente(ctx: Any, cid: str | None, texto: str) -> None:
    """HG-21 / Q9: o cliente com aprovação parada recebe "seu caso segue em análise",
    uma vez por lembrete (a chave do lembrete já impede repetição)."""
    ferramentas = getattr(ctx, "ferramentas", None)
    if not cid or ferramentas is None:
        return
    ferramentas.executar(
        AcaoProposta(
            ferramenta="responder_cliente",
            papel=Papel.ATENDENTE,
            executado_por="agente",
            conversation_id=cid,
            motivo=texto,
        )
    )


def _conversa_da_aprovacao(ctx: Any, aprovacao_id: str) -> str | None:
    base = ctx.base
    with getattr(base, "trava", None) or nullcontext():
        linha = base.conexao.execute(
            "SELECT acao FROM aprovacoes WHERE aprovacao_id = ?", (aprovacao_id,)
        ).fetchone()
    if linha is None:
        return None
    return json.loads(linha[0] or "{}").get("conversation_id")
