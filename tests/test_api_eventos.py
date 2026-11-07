"""SSE /api/eventos encerra quando o cliente desconecta ou o servidor desliga (--reload travava)."""

import asyncio

from atendimento.api.app import fluxo_eventos


async def _coletar(gerador, maximo=10):
    saida = []
    async for item in gerador:
        saida.append(item)
        if len(saida) >= maximo:
            break
    return saida


def test_sse_termina_quando_o_cliente_desconecta():
    chamadas = {"n": 0}

    async def desconectado():
        chamadas["n"] += 1
        return chamadas["n"] > 1  # desconecta depois do primeiro evento

    eventos = [{"tipo": "acao", "payload": {}}]
    saida = asyncio.run(
        asyncio.wait_for(
            _coletar(fluxo_eventos(eventos, 0, None, desconectado, asyncio.Event(), 0.01)), 2
        )
    )
    assert len(saida) == 1


def test_sse_termina_no_desligamento_do_servidor():
    async def nunca():
        return False

    async def rodar():
        parar = asyncio.Event()
        parar.set()
        return await _coletar(fluxo_eventos([], 0, None, nunca, parar, 0.01))

    assert asyncio.run(asyncio.wait_for(rodar(), 2)) == []


def test_sse_de_um_app_novo_nao_herda_o_desligamento_de_outro_app():
    from fastapi.testclient import TestClient
    from fixtures.agente.falsos import BaseFalsa, FerramentasFalsas

    from atendimento.agente.caso import Agente
    from atendimento.api.app import criar_app

    base = BaseFalsa()
    base.conversa("AT1", [])
    with TestClient(criar_app(Agente(base, FerramentasFalsas(base)))):
        pass  # lifespan do primeiro app termina
    agente = Agente(base, FerramentasFalsas(base))
    agente.processar("AT1")
    cliente = TestClient(criar_app(agente))
    with cliente.stream("GET", "/api/eventos?desde=0&limite=1") as resposta:
        corpo = "".join(resposta.iter_text())
    assert corpo.count("data: ") == 1
