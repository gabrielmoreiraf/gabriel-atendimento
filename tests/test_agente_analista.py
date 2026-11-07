"""HG-19 / HG-16: o agente de atendimento chama o agente analista em cobrança em dobro e
contato repetido, e registra o resultado no caso e no canal."""

from fixtures.agente.falsos import BaseFalsa, FerramentasFalsas, ReplayFalso, pedido

from atendimento.agente.caso import Agente


class AnalistaFalso:
    def __init__(self, incidente_id="INC-000001"):
        self.chamadas = []
        self.incidente_id = incidente_id

    def __call__(self, *, fator, order_ids, conversation_ids):
        self.chamadas.append((fator, tuple(order_ids), tuple(conversation_ids)))
        incidente = {"incidente_id": self.incidente_id} if self.incidente_id else None
        return {"fator": fator, "incidente": incidente}


def test_HG_19_cobranca_em_dobro_chama_o_analista_e_avisa_o_canal():
    base = BaseFalsa()
    base.conversa("AT1", ["Paguei o boleto e cobraram no cartão também."], order_id="GBH1")
    base.com_pedido(pedido("GBH1", valor=80.0))
    analista = AnalistaFalso()
    agente = Agente(base, FerramentasFalsas(base), analista=analista)
    caso = agente.processar("AT1")
    assert analista.chamadas == [("cobranca_em_dobro", ("GBH1",), ("AT1",))]
    assert caso.analista[0]["incidente"]["incidente_id"] == "INC-000001"
    assert any("chamou o agente analista: incidente INC-000001" in m["texto"] for m in agente.canal)


def test_HG_16_pedido_com_conversa_anterior_chama_analista_de_contato_repetido():
    base = BaseFalsa()
    base.conversa("AT2", ["Meu pedido era pra ter chegado e nada"], order_id="GBH2")
    base.com_pedido(pedido("GBH2", valor=80.0))
    replay = ReplayFalso(base)
    replay.historica("AT_ANTIGA", ["cadê meu pedido?"], "GBH2", "2026-10-25 10:00:00")
    analista = AnalistaFalso(incidente_id=None)
    agente = Agente(base, FerramentasFalsas(base), replay=replay, analista=analista)
    caso = agente.processar("AT2")
    assert analista.chamadas == [("contato_repetido", ("GBH2",), ("AT2", "AT_ANTIGA"))]
    assert any("sem padrão de causa comum" in m["texto"] for m in agente.canal)
    assert caso.estado == "resolvida"


def test_HG_19_conversa_comum_nao_chama_analista():
    base = BaseFalsa()
    base.conversa("AT3", ["Meu pedido era pra ter chegado e nada"], order_id="GBH3")
    base.com_pedido(pedido("GBH3", valor=80.0))
    analista = AnalistaFalso()
    Agente(base, FerramentasFalsas(base), replay=ReplayFalso(base), analista=analista).processar(
        "AT3"
    )
    assert analista.chamadas == []
