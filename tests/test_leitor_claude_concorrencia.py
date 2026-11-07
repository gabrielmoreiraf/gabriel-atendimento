"""A chamada ao modelo nunca acontece com a trava segura: a fila é lida antes (até 8 em
paralelo) e só a decisão e a execução rodam dentro da trava. Leitor falso lento, sem rede."""

import threading
import time

import pytest
from fastapi.testclient import TestClient
from fixtures.agente.falsos import BaseFalsa, FerramentasFalsas, pedido

from atendimento.agente.caso import Agente, RodadaEmAndamento
from atendimento.agente.leitor import ler
from atendimento.api.app import criar_app

ATRASO = 0.3
N = 16


class LeitorLento:
    def __init__(self, atraso=ATRASO):
        self.atraso = atraso
        self.lidos: list[str] = []
        self._trava = threading.Lock()

    def __call__(self, texto, *, cupons=None):
        time.sleep(self.atraso)
        with self._trava:
            self.lidos.append(texto)
        return ler(texto, cupons=cupons)


def _base(n=N):
    base = BaseFalsa()
    for i in range(n):
        base.conversa(
            f"AT{i:03d}", [f"Cadê o rastreio do pedido GBH{i:06d}?"], order_id=f"GBH{i:06d}"
        )
        base.com_pedido(pedido(f"GBH{i:06d}", valor=80.0))
    base.conversa("AT_BOT", [])  # só o bot falou: não chama o leitor
    return base


def _em_segundo_plano(funcao):
    resultado = {}

    def rodar():
        resultado["valor"] = funcao()

    fio = threading.Thread(target=rodar)
    fio.start()
    return fio, resultado


def test_HG_13_placar_e_fila_respondem_enquanto_a_fila_e_lida():
    base = _base()
    agente = Agente(base, FerramentasFalsas(base), leitor=LeitorLento())
    fio, _ = _em_segundo_plano(agente.processar_fila)
    time.sleep(0.05)
    esperas = []
    while fio.is_alive():
        inicio = time.perf_counter()
        agente.placar()
        agente.fila()
        esperas.append(time.perf_counter() - inicio)
        time.sleep(0.02)
    fio.join()
    assert esperas and max(esperas) < 0.5


def test_leitura_em_paralelo_termina_em_fracao_do_tempo_sequencial():
    base = _base()
    leitor = LeitorLento()
    agente = Agente(base, FerramentasFalsas(base), leitor=leitor)
    inicio = time.perf_counter()
    agente.processar_fila()
    decorrido = time.perf_counter() - inicio
    sequencial = N * ATRASO
    assert decorrido < sequencial / 3
    assert len(leitor.lidos) == N  # AT_BOT não chama o leitor


def test_nada_e_processado_duas_vezes():
    base = _base()
    leitor = LeitorLento(atraso=0.01)
    agente = Agente(base, FerramentasFalsas(base), leitor=leitor)
    agente.processar_fila()
    total = len(base.registros)
    agente.processar_fila()
    agente.processar("AT000")
    assert len(base.registros) == total
    assert len(leitor.lidos) == N
    classificadas = [r.conversation_id for r in base.registros if r.acao == "classificar_conversa"]
    assert len(classificadas) == len(set(classificadas)) == N + 1


def test_rodada_em_andamento_recusa_outra():
    base = _base()
    agente = Agente(base, FerramentasFalsas(base), leitor=LeitorLento())
    fio, _ = _em_segundo_plano(agente.processar_fila)
    time.sleep(0.05)
    with pytest.raises(RodadaEmAndamento):
        agente.processar_fila()
    resposta = TestClient(criar_app(agente)).post("/api/fila/processar")
    assert resposta.status_code == 409
    fio.join()


def test_evento_leitura_com_progresso():
    base = _base()
    agente = Agente(base, FerramentasFalsas(base), leitor=LeitorLento(atraso=0.01))
    agente.processar_fila()
    progresso = [e["payload"] for e in agente.eventos if e["tipo"] == "leitura"]
    assert progresso[-1] == {"lidas": N + 1, "total": N + 1}
    assert [p["lidas"] for p in progresso] == list(range(1, N + 2))


def test_processar_uma_conversa_le_fora_da_trava():
    base = _base()
    agente = Agente(base, FerramentasFalsas(base), leitor=LeitorLento(atraso=0.6))
    fio, _ = _em_segundo_plano(lambda: agente.processar("AT000"))
    time.sleep(0.1)
    inicio = time.perf_counter()
    agente.placar()
    assert time.perf_counter() - inicio < 0.3
    fio.join()
    assert agente.casos["AT000"].estado == "resolvida"


def test_leitor_por_regras_mesmo_resultado_em_lote_e_uma_a_uma():
    base_lote, base_uma = _base(), _base()
    lote = Agente(base_lote, FerramentasFalsas(base_lote))
    placar_lote = lote.processar_fila()
    uma = Agente(base_uma, FerramentasFalsas(base_uma))
    for conversa in uma.fila():
        uma.processar(conversa["conversation_id"])
    assert placar_lote == uma.placar()
    assert [(r.conversation_id, r.acao) for r in base_lote.registros] == [
        (r.conversation_id, r.acao) for r in base_uma.registros
    ]
