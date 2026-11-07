"""API do agente para a interface (contrato W4 ↔ W5 em `SPEC.md`, seção "API").

Subida: `uv run uvicorn atendimento.api.app:app --port 8000`. A cada subida,
`var/atendimento.db` é recriado a partir de `docs/` (somente leitura) pela carga do W1. Caminhos podem ser
trocados por `ATENDIMENTO_DB` e `ATENDIMENTO_DOCS`.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from atendimento.agente.aprovacoes import AprovacaoInvalida, AprovacaoRecusada
from atendimento.agente.caso import Agente, RodadaEmAndamento
from atendimento.agente.leitor import escolher_leitor, ler
from atendimento.api.analista import criar_router as criar_router_analista
from atendimento.api.vigia import criar_router as criar_router_vigia

RAIZ = Path(__file__).resolve().parents[3]

# Desligamento: o --reload do uvicorn espera as conexões abertas fecharem antes do lifespan,
# e o SSE nunca fechava. Avisamos o gerador já no sinal de saída do uvicorn (como faz o
# sse-starlette) e também no fim do lifespan.
DESLIGANDO = threading.Event()


def _avisar_desligamento_no_uvicorn() -> None:
    try:
        from uvicorn.server import Server
    except ImportError:  # pragma: no cover - uvicorn é dependência do projeto
        return
    original = Server.handle_exit
    if getattr(original, "_avisa_sse", False):
        return

    def handle_exit(self, *args, **kwargs):
        DESLIGANDO.set()
        return original(self, *args, **kwargs)

    handle_exit._avisa_sse = True
    Server.handle_exit = handle_exit


_avisar_desligamento_no_uvicorn()


class _Parar:
    def __init__(self, local: threading.Event):
        self.local = local

    def is_set(self) -> bool:
        return DESLIGANDO.is_set() or self.local.is_set()


async def fluxo_eventos(lista, desde, limite, desconectado, parar, intervalo=0.25):
    """Gerador SSE `{tipo, payload}`: termina no `limite`, quando o cliente desconecta
    (`desconectado()`) ou quando o servidor está desligando (`parar.is_set()`)."""
    indice = len(lista) if desde is None else desde
    enviados = 0
    while limite is None or enviados < limite:
        if parar.is_set() or await desconectado():
            return
        if indice < len(lista):
            evento = jsonable_encoder(lista[indice])
            yield f"id: {indice}\ndata: {json.dumps(evento, ensure_ascii=False)}\n\n"
            indice += 1
            enviados += 1
        else:
            await asyncio.sleep(intervalo)


class CorpoAprovar(BaseModel):
    supervisor_id: str
    comentario: str | None = None


class CorpoDecidirSuspeita(BaseModel):
    supervisor_id: str
    decisao: Literal["procedente", "improcedente"]
    justificativa: str


class CorpoRejeitar(BaseModel):
    supervisor_id: str
    justificativa: str


def agente_real() -> Agente:
    from atendimento.dados.carga import carregar
    from atendimento.dados.repositorio import Base
    from atendimento.ferramentas import Ferramentas

    db = Path(os.environ.get("ATENDIMENTO_DB", RAIZ / "var" / "atendimento.db"))
    # HG-12: o estado do agente vive em memória; a base é recriada a cada subida para que
    # um --reload não deixe ações antigas no log e faça a fila ser tratada duas vezes.
    carregar(Path(os.environ.get("ATENDIMENTO_DOCS", RAIZ / "docs")), db)
    base = Base(db)
    # ATENDIMENTO_LLM=1 liga o leitor com Claude; sem ela, o leitor por regras (padrão)
    leitor = escolher_leitor()
    return Agente(base, Ferramentas(base), leitor=None if leitor is ler else leitor)


CAMPOS_FILA = (
    "conversation_id",
    "canal",
    "marca",
    "assunto",
    "order_id",
    "data_abertura",
    "prioridade",
    "estado",
    "vencimento_sla",
    "sla_vencido",
)


def criar_app(agente: Agente | None = None) -> FastAPI:
    estado: dict[str, Agente] = {}
    # desligamento deste app (lifespan); o DESLIGANDO global vem do sinal de saída do uvicorn
    desligando_app = threading.Event()
    parar = _Parar(desligando_app)
    if agente is not None:
        estado["agente"] = agente

    @asynccontextmanager
    async def ciclo(_app: FastAPI):
        if "agente" not in estado:
            estado["agente"] = agente_real()
        estado["agente"].obter_analista()  # cria o único Analista do processo na subida
        yield
        desligando_app.set()

    app = FastAPI(title="Atendimento ao Cliente: agente", lifespan=ciclo)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def ag() -> Agente:
        return estado["agente"]

    app.include_router(criar_router_analista(ag))
    app.include_router(criar_router_vigia(ag))

    def detalhe(cid: str) -> dict:
        try:
            return jsonable_encoder(ag().detalhe(cid))
        except KeyError as erro:
            raise HTTPException(404, f"conversa {cid} não está na fila") from erro

    @app.get("/api/fila")
    def fila() -> list[dict]:
        return jsonable_encoder([{k: c.get(k) for k in CAMPOS_FILA} for c in ag().fila()])

    @app.post("/api/fila/processar")
    def processar_fila() -> dict:
        try:
            return ag().processar_fila()
        except RodadaEmAndamento as erro:
            raise HTTPException(409, str(erro)) from erro

    @app.post("/api/conversas/{cid}/processar")
    def processar_conversa(cid: str) -> dict:
        agente_atual = ag()
        detalhe(cid)  # 404 se não existe
        if cid not in agente_atual.casos:  # não repete ações de um caso já tratado
            agente_atual.processar(cid)
        return detalhe(cid)

    @app.get("/api/conversas/{cid}")
    def conversa(cid: str) -> dict:
        return detalhe(cid)

    @app.get("/api/acoes")
    def acoes() -> list[dict]:
        return ag().acoes()

    @app.get("/api/canal")
    def canal() -> list[dict]:
        return ag().canal

    def _decidir(funcao, aprovacao_id: str, *args) -> dict:
        try:
            caso = funcao(aprovacao_id, *args)
        except KeyError as erro:
            raise HTTPException(404, f"aprovação {aprovacao_id} não existe") from erro
        except (AprovacaoRecusada, PermissionError) as erro:  # inclui FerramentaNaoPermitida
            raise HTTPException(403, str(erro)) from erro
        except (AprovacaoInvalida, ValueError) as erro:  # aprovação já decidida, inválida
            raise HTTPException(409, str(erro)) from erro
        return detalhe(caso.conversation_id)

    @app.post("/api/aprovacoes/{aprovacao_id}/aprovar")
    def aprovar(aprovacao_id: str, corpo: CorpoAprovar) -> dict:
        return _decidir(ag().aprovar, aprovacao_id, corpo.supervisor_id, corpo.comentario or "")

    @app.post("/api/aprovacoes/{aprovacao_id}/rejeitar")
    def rejeitar(aprovacao_id: str, corpo: CorpoRejeitar) -> dict:
        return _decidir(ag().rejeitar, aprovacao_id, corpo.supervisor_id, corpo.justificativa)

    @app.get("/api/replay/casos")
    def replay_casos() -> list[dict]:
        """F3: conversas do histórico com anexo, com a suspeita prevista pelo verificador."""
        return jsonable_encoder(ag().casos_replay())

    @app.post("/api/replay/{cid}/processar")
    def replay_processar(cid: str) -> dict:
        """F3: processa a conversa histórica com agora = data_abertura; marcada como replay."""
        try:
            ag().processar_replay(cid)
        except KeyError as erro:
            raise HTTPException(404, f"conversa {cid} não está no histórico") from erro
        return detalhe(cid)

    @app.get("/api/suspeitas")
    def suspeitas() -> list[dict]:
        """Suspeitas pendentes com o prazo (sinalizada_em + prazo_decisao_horas)."""
        return jsonable_encoder(ag().suspeitas_pendentes())

    @app.post("/api/suspeitas/{suspeita_id}/decidir")
    def decidir_suspeita(suspeita_id: str, corpo: CorpoDecidirSuspeita) -> dict:
        try:
            caso = ag().decidir_suspeita(
                suspeita_id, corpo.supervisor_id, corpo.decisao, corpo.justificativa
            )
        except KeyError as erro:
            raise HTTPException(404, f"suspeita {suspeita_id} não existe") from erro
        except (AprovacaoRecusada, PermissionError) as erro:  # HG-04: quem sinalizou não decide
            raise HTTPException(403, str(erro)) from erro
        except ValueError as erro:
            raise HTTPException(409, str(erro)) from erro
        return detalhe(caso.conversation_id)

    @app.get("/api/placar")
    def placar() -> dict:
        return ag().placar()

    @app.get("/api/eventos")
    async def eventos(
        request: Request, desde: int | None = None, limite: int | None = None
    ) -> StreamingResponse:
        """SSE `{tipo, payload}`. `desde` (índice) e `limite` servem para retomar e testar."""
        return StreamingResponse(
            fluxo_eventos(ag().eventos, desde, limite, request.is_disconnected, parar),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    return app


app = criar_app()
