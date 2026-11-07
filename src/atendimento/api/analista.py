"""Rotas do agente analista (HG-17, HG-19, HG-23): padrões de causa comum e incidentes.

Plugar no app: `app.include_router(criar_router(ag))`, em que `ag()` devolve um objeto com
`base` e `ferramentas` (o `Agente` do W4). Se ele tiver `emitir` e `postar_no_canal`, cada
incidente vira evento SSE (`tipo = "incidente"`) e mensagem no canal do time.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder

from atendimento.analista import Analista, Padrao, ResultadoAnalista, detectar_padroes
from atendimento.ferramentas import mascarar_texto


def _mascarar(valor: Any) -> Any:
    """Dados pessoais (CPF, cartão, telefone) mascarados em todo texto da resposta."""
    if isinstance(valor, str):
        return mascarar_texto(valor)
    if isinstance(valor, dict):
        return {k: _mascarar(v) for k, v in valor.items()}
    if isinstance(valor, list | tuple):
        return [_mascarar(v) for v in valor]
    return valor


def serializar_padrao(padrao: Padrao) -> dict:
    return _mascarar(jsonable_encoder(asdict(padrao)))


def serializar_resultado(resultado: ResultadoAnalista, *, ja_tratado: bool = False) -> dict:
    corpo = {
        "padrao": asdict(resultado.padrao) if resultado.padrao else None,
        "incidente": resultado.incidente,
        "notificacoes": resultado.notificacoes,
        "sem_consentimento": resultado.sem_consentimento,
        "adiados": resultado.adiados,
        "aviso_ao_time": asdict(resultado.aviso_ao_time) if resultado.aviso_ao_time else None,
        "detalhes": resultado.detalhes,
        "ja_tratado": ja_tratado,
    }
    return _mascarar(jsonable_encoder(corpo))


def criar_router(obter_contexto: Callable[[], Any]) -> APIRouter:
    router = APIRouter(prefix="/api/analista", tags=["analista"])
    # Um único Analista por processo: vale o máximo de avisos por dia (ferramentas.csv).
    estado: dict[str, Any] = {"analista": None}
    trava_local = threading.RLock()

    def contexto() -> Any:
        return obter_contexto()

    def trava(ctx: Any):
        return getattr(ctx.base, "trava", None) or nullcontext()

    def analista(ctx: Any) -> Analista:
        # Usa o Analista do agente quando há (um só contador de avisos por processo).
        compartilhado = getattr(ctx, "obter_analista", None)
        if compartilhado is not None and compartilhado() is not None:
            return compartilhado()
        if estado["analista"] is None:
            estado["analista"] = Analista(ctx.base, ctx.ferramentas)
        return estado["analista"]

    @router.get("/padroes")
    def padroes(ctx: Any = Depends(contexto)) -> list[dict]:  # noqa: B008
        with trava(ctx):
            return [serializar_padrao(p) for p in detectar_padroes(ctx.base)]

    @router.post("/padroes/{tipo}/tratar")
    def tratar(tipo: str, ctx: Any = Depends(contexto)) -> dict:  # noqa: B008
        with trava_local, trava(ctx):
            padrao = next((p for p in detectar_padroes(ctx.base) if p.tipo == tipo), None)
            if padrao is None:
                raise HTTPException(404, f"padrão {tipo} não encontrado na base")
            # Q22: o Analista guarda o incidente do (tipo, dia) e não reavisa ninguém.
            resultado = analista(ctx).tratar(padrao)
        ja_tratado = bool(resultado.detalhes.get("reaproveitado"))
        if resultado.incidente is None or ja_tratado:
            return serializar_resultado(resultado, ja_tratado=ja_tratado)
        incidente = resultado.incidente
        resumo = {
            "incidente_id": incidente.get("incidente_id"),
            "tipo": tipo,
            "pedidos": len(padrao.escopo),
            "avisos": len(resultado.notificacoes),
            "sem_consentimento": len(resultado.sem_consentimento),
            "adiados": len(resultado.adiados),
        }
        if hasattr(ctx, "emitir"):
            ctx.emitir("incidente", resumo)
        if hasattr(ctx, "postar_no_canal"):
            ctx.postar_no_canal(
                "aviso",
                None,
                f"Agente analista abriu {resumo['incidente_id']} ({tipo}): "
                f"{resumo['pedidos']} pedidos, {resumo['avisos']} avisos enviados, "
                f"{resumo['sem_consentimento']} sem consentimento, {resumo['adiados']} para amanhã.",
                None,
                incidente_id=resumo["incidente_id"],
            )
        return serializar_resultado(resultado)

    return router
