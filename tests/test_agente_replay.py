"""Modo replay: reprocessa conversas do histórico com anexo no "agora" em que chegaram (F3)."""

from datetime import date, datetime

import pytest
from fixtures.agente.falsos import (
    BaseFalsa,
    FerramentasFalsas,
    ReplayFalso,
    anexo,
    pedido,
)

from atendimento.agente.caso import Agente
from atendimento.contratos import AGORA, FUSO, Resultado


def _cenario():
    base = BaseFalsa()
    base.conversa("AT_HOJE", ["Cadê o rastreio?"], order_id="GBH000001")
    base.com_pedido(pedido("GBH000001", valor=120.0))
    replay = ReplayFalso(base)
    replay.historica("AT104936", ["A capinha chegou quebrada."], "GCH1", "2026-08-06 15:53:56")
    base.com_pedido(pedido("GCH1", valor=89.9, entrega=date(2026, 8, 4)))
    base.com_anexo(anexo("AT104936", "GCH1", captura=datetime(2026, 8, 5, 10, 0, tzinfo=FUSO)))
    replay.historica("AT_SEM_ANEXO", ["oi"], "GCH2", "2026-08-07 10:00:00")
    ferramentas = FerramentasFalsas(base)
    return base, ferramentas, Agente(base, ferramentas, replay=replay)


def test_F3_replay_lista_so_conversas_com_anexo_e_preve_suspeita():
    _, _, agente = _cenario()
    casos = agente.casos_replay()
    assert [c["conversation_id"] for c in casos] == ["AT104936"]
    assert casos[0]["suspeita_prevista"] is False
    assert casos[0]["n_anexos"] == 1


def test_F3_replay_usa_agora_da_abertura_e_fica_marcado():
    base, ferramentas, agente = _cenario()
    caso = agente.processar_replay("AT104936")
    assert caso.replay is True
    assert caso.decisao.resultado is Resultado.EXECUTAR  # 2 dias após a entrega
    reenvio = next(r for r in caso.acoes if r.acao == "reenviar_produto")
    assert reenvio.data_hora == datetime(2026, 8, 6, 15, 53, 56, tzinfo=FUSO)
    assert agente.agora == AGORA and ferramentas.agora == AGORA  # restaurado
    assert all(m["replay"] for m in agente.canal if m["conversation_id"] == "AT104936")


def test_F3_replay_nao_afeta_a_fila_nem_o_placar_de_hoje():
    _, _, agente = _cenario()
    agente.processar_replay("AT104936")
    assert [c["conversation_id"] for c in agente.fila()] == ["AT_HOJE"]
    assert agente.fila()[0]["estado"] == "aberta"
    placar = agente.placar()
    assert placar["resolvidas_sozinho"] == 0
    assert placar["replay"]["resolvidas_sozinho"] == 1
    assert placar["replay"]["valor_executado_rs"] == 89.9


def test_F3_replay_de_conversa_desconhecida_e_erro():
    _, _, agente = _cenario()
    with pytest.raises(KeyError):
        agente.processar_replay("AT_NAO_EXISTE")


def test_F3_aprovacao_de_caso_replay_roda_no_momento_da_abertura():
    base = BaseFalsa()
    replay = ReplayFalso(base)
    replay.historica("AT_R", ["O pote chegou amassado."], "GBH9", "2026-08-06 15:00:00")
    base.com_pedido(pedido("GBH9", valor=260.0, entrega=date(2026, 8, 4)))
    base.com_anexo(anexo("AT_R", "GBH9", captura=datetime(2026, 8, 5, 9, 0, tzinfo=FUSO)))
    agente = Agente(base, FerramentasFalsas(base), replay=replay)
    caso = agente.processar_replay("AT_R")
    assert caso.estado == "aguardando_aprovacao"
    aprovacao_id = caso.aprovacao_ids[0]
    caso = agente.aprovar(aprovacao_id, "supervisor_01")
    assert "reenviar_produto" in [r.acao for r in caso.acoes]
    assert agente.agora == AGORA
