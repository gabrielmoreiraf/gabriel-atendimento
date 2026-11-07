"""HG-16: em pedido que já teve conversa, o agente carrega as ações feitas e não as repete."""

from fixtures.agente.falsos import BaseFalsa, FerramentasFalsas, ReplayFalso, anexo, captura, pedido

from atendimento.agente.caso import Agente
from atendimento.contratos import AcaoAnterior, Item


def _cenario(textos, historico_acao):
    base = BaseFalsa()
    base.conversa("AT_NOVA", textos, order_id="GBH1")
    base.com_pedido(pedido("GBH1", valor=120.0))
    replay = ReplayFalso(base)
    replay.historica("AT_ANTIGA", ["primeiro contato"], "GBH1", "2026-10-28 10:00:00")
    replay.historico_acoes.append(
        {
            "acao_id": "AC000777",
            "order_id": "GBH1",
            "conversation_id": "AT_ANTIGA",
            "acao": historico_acao,
            "data_hora": "2026-10-28 10:30:00",
            "referencia_sistema": "CHM-000777",
        }
    )
    return base, Agente(base, FerramentasFalsas(base), replay=replay)


def test_HG_16_nao_abre_segundo_chamado_com_a_transportadora():
    base, agente = _cenario(
        ["Meu pedido era pra ter chegado e nada."], "abrir_chamado_transportadora"
    )
    caso = agente.processar("AT_NOVA")
    assert "abrir_chamado_transportadora" not in [r.acao for r in caso.acoes]
    assert "CHM-000777" in caso.resposta_ao_cliente
    assert "28/10/2026" in caso.resposta_ao_cliente
    assert any("HG-16" in m["texto"] for m in agente.canal)


def test_HG_22_reenvio_quebrou_de_novo_com_reenvio_anterior_de_150_pede_aprovacao():
    """Q23: ação com dinheiro nunca é barrada pelo HG-16; passa pela política com o acumulado."""
    base, agente = _cenario(["O body mist chegou vazando de novo."], "reenviar_produto")
    base.com_dinheiro_anterior(
        AcaoAnterior("AC000777", "GBH1", "reenviar_produto", 150.0, "atendente_02", None)
    )
    base.com_anexo(anexo("AT_NOVA", "GBH1", captura=captura(31)))
    caso = agente.processar("AT_NOVA")
    assert "reenviar_produto" not in [r.acao for r in caso.acoes]
    assert "solicitar_aprovacao" in [r.acao for r in caso.acoes]
    assert caso.estado == "aguardando_aprovacao"
    assert caso.decisao.detalhes["acumulado_rs"] == 150.0


def test_HG_16_acao_diferente_da_ja_feita_segue_normal():
    base, agente = _cenario(["Meu pedido era pra ter chegado e nada."], "informar_status")
    caso = agente.processar("AT_NOVA")
    assert "abrir_chamado_transportadora" in [r.acao for r in caso.acoes]


def test_HG_16_duas_demandas_da_mesma_conversa_nao_se_bloqueiam():
    base = BaseFalsa()
    base.conversa(
        "AT1",
        ["Faltou a necessaire de brinde. Ah, e a caixa veio amassada, com o produto danificado"],
        order_id="GBH8",
    )
    itens = (
        Item("GBH8-1", "KSH-1", "Body Mist", "venda", 120.0, None),
        Item("GBH8-2", "GBT-9001", "Necessaire GoBeauté", "brinde", 0.0, None),
    )
    base.com_pedido(pedido("GBH8", valor=120.0, itens=itens))
    base.com_anexo(anexo("AT1", "GBH8", captura=captura(31)))
    caso = Agente(base, FerramentasFalsas(base), replay=ReplayFalso(base)).processar("AT1")
    assert len([r for r in caso.acoes if r.acao == "reenviar_produto"]) == 2
