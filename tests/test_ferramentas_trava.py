"""HG-12: Ferramentas usa a mesma conexão SQLite da Base, então passa pela mesma trava.

A API roda as rotas síncronas em threads; sem a trava, um GET /api/acoes concorre com o
processamento na mesma conexão (o E2E já viu IndexError por isso em Base.fila()).
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from atendimento.contratos import AcaoProposta, Papel
from atendimento.dados.carga import carregar
from atendimento.dados.repositorio import Base
from atendimento.ferramentas import Ferramentas

FIXTURES = Path(__file__).parent / "fixtures" / "dados"


@pytest.fixture
def base(tmp_path):
    caminho = tmp_path / "base.db"
    carregar(FIXTURES, caminho)
    return Base(caminho)


def _reenvio(conversa: str, valor: float = 50.0) -> AcaoProposta:
    return AcaoProposta(
        ferramenta="reenviar_produto",
        papel=Papel.ATENDENTE,
        executado_por="agente",
        conversation_id=conversa,
        order_id="GBH473217",
        valor_rs=valor,
        motivo="extravio",
    )


CHAMADAS = {
    "executar": lambda f: f.executar(_reenvio("AT999100")),
    "consultar_rastreio": lambda f: f.consultar_rastreio("GBH473217"),
    "verificar_pagamento": lambda f: f.verificar_pagamento("GBH473217"),
    "aprovacao": lambda f: f.aprovacao("APR-000001"),
    "acoes_registradas": lambda f: f.acoes_registradas(),
}


@pytest.mark.parametrize("nome", sorted(CHAMADAS))
def test_HG_12_ferramentas_esperam_a_trava_da_base(base, nome):
    ferramentas = Ferramentas(base)
    terminou = threading.Event()

    def chamar():
        CHAMADAS[nome](ferramentas)
        terminou.set()

    with base.trava:  # outra thread está usando a conexão
        outra = threading.Thread(target=chamar)
        outra.start()
        assert not terminou.wait(0.3), f"{nome} acessou a conexão sem a trava"
    outra.join(5)
    assert terminou.is_set()


def test_HG_12_escritas_e_leituras_concorrentes_sem_erro(base):
    ferramentas = Ferramentas(base)

    def trabalho(i: int):
        if i % 2:
            return len(ferramentas.acoes_registradas())
        return ferramentas.executar(_reenvio(f"AT9{i:05d}", valor=10.0 + i)).acao_id

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(trabalho, range(120)))

    ids = [r.acao_id for r in ferramentas.acoes_registradas()]
    assert len(ids) == 60
    assert len(set(ids)) == 60  # nenhum acao_id repetido por corrida em _proximo
