"""Dúvida de produto e cupom com as ferramentas do catálogo (responder_duvida, validar_cupom)."""

from fixtures.agente.falsos import BaseFalsa, FerramentasFalsas, pedido

from atendimento.agente.caso import Agente


def _agente(textos, order_id="GBH1"):
    base = BaseFalsa()
    base.conversa("AT1", textos, order_id=order_id)
    base.com_pedido(pedido("GBH1", valor=80.0))
    ferramentas = FerramentasFalsas(base)
    return base, ferramentas, Agente(base, ferramentas)


def _forcar(monkeypatch, categoria, **campos):
    from dataclasses import replace

    import atendimento.agente.caso as caso_mod

    original = caso_mod.ler
    monkeypatch.setattr(
        caso_mod,
        "ler",
        lambda t, **kw: replace(original(t, **kw), categoria=categoria, **campos),
    )


def test_duvida_de_produto_respondida_pela_ficha_sem_escalar(monkeypatch):
    _forcar(monkeypatch, "duvida_produto")
    _, ferramentas, agente = _agente(["O body mist pode usar todo dia?"])
    ferramentas.fichas["KSH-1"] = "Pode usar diariamente."
    caso = agente.processar("AT1")
    assert ferramentas.duvidas_respondidas == [("AT1", "KSH-1")]
    acoes = [r.acao for r in caso.acoes]
    assert "acionar_pessoa" not in acoes
    assert "responder_cliente" not in acoes  # a ferramenta já respondeu ao cliente
    assert caso.estado == "resolvida"
    assert caso.resposta_ao_cliente == "Pode usar diariamente."


def test_duvida_sem_ficha_escala(monkeypatch):
    _forcar(monkeypatch, "duvida_produto")
    _, _, agente = _agente(["O body mist pode usar todo dia?"])
    caso = agente.processar("AT1")
    assert "acionar_pessoa" in [r.acao for r in caso.acoes]
    assert caso.estado == "escalada"


def test_cupom_invalido_responde_com_o_motivo(monkeypatch):
    _forcar(monkeypatch, "cupom_promocao")
    _, ferramentas, agente = _agente(["Usei o cupom VOLTA15 mas não descontou no total"])
    ferramentas.cupons["VOLTA15"] = {
        "valido": False,
        "motivo": "nao_acumula_com_outra_promocao",
        "detalhe": "O cupom VOLTA15 não acumula com outra promoção já aplicada ao pedido.",
    }
    caso = agente.processar("AT1")
    assert "não acumula" in caso.resposta_ao_cliente
    assert "acionar_pessoa" not in [r.acao for r in caso.acoes]
    assert caso.estado == "resolvida"


def test_cupom_valido_nao_aplicado_escala_para_o_comercial(monkeypatch):
    _forcar(monkeypatch, "cupom_promocao")
    _, ferramentas, agente = _agente(["Usei o cupom VOLTA15 mas não descontou no total"])
    ferramentas.cupons["VOLTA15"] = {"valido": True, "motivo": "", "detalhe": "Cupom válido."}
    caso = agente.processar("AT1")
    assert ("acionar_pessoa", "comercial") in ferramentas.areas
    assert caso.estado == "escalada"


def test_codigo_do_cupom_vem_da_lista_de_cupons_da_base(monkeypatch):
    _forcar(monkeypatch, "cupom_promocao")
    base = BaseFalsa()
    base.codigos_cupom = lambda: ["BEMVINDA10"]
    base.conversa("AT1", ["Usei BEMVINDA10 e não descontou"], order_id="GBH1")
    base.com_pedido(pedido("GBH1", valor=80.0))
    ferramentas = FerramentasFalsas(base)
    ferramentas.cupons["BEMVINDA10"] = {"valido": False, "motivo": "x", "detalhe": "Expirado."}
    caso = Agente(base, ferramentas).processar("AT1")
    assert "BEMVINDA10" in caso.resposta_ao_cliente
    assert caso.estado == "resolvida"


def test_HP_08_cupom_e_duvida_escalados_nao_duplicam_o_encaminhamento_nem_prometem(monkeypatch):
    _forcar(monkeypatch, "cupom_promocao", categoria_secundaria="duvida_produto")
    _, ferramentas, agente = _agente(["O cupom BEMVINDA10 não funcionou. A garrafa vaza?"])
    ferramentas.cupons["BEMVINDA10"] = {"valido": True, "motivo": "", "detalhe": "Cupom ativo."}
    caso = agente.processar("AT1")
    resposta = caso.resposta_ao_cliente
    assert caso.estado == "escalada"
    assert resposta.count("por aqui") == 1
    assert "vai ajustar" not in resposta and "ajustar o desconto" not in resposta
    assert "comercial" in resposta
