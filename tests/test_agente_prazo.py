"""HP-04: reenvio de avaria dentro da alçada responde com o prazo e encerra com tag Avaria."""

from datetime import date, datetime

from fixtures.agente.falsos import BaseFalsa, FerramentasFalsas, anexo, captura, pedido, politicas

from atendimento.agente.caso import Agente, prazo_de_entrega
from atendimento.contratos import AGORA, FUSO, Item


def test_HP_04_prazo_conta_dias_uteis_sem_feriado_a_partir_do_dia_seguinte():
    # 02/11/2026 (segunda, feriado) 08h + 1 dia útil de preparo GoBeauté + 2 da ViaLog no SE
    p = pedido("GBH1", marca="Kokeshi")
    bruto = {"transportadora": "ViaLog", "uf": "SP"}
    assert prazo_de_entrega(p, bruto, politicas(), AGORA) == date(2026, 11, 5)


def test_HP_04_gocase_personalizado_tem_3_dias_de_preparo_e_pula_fim_de_semana():
    itens = (Item("GCH1-1", "GC-1", "Capinha", "venda", 89.9, "Ana"),)
    p = pedido("GCH1", marca="Gocase", itens=itens)
    bruto = {"transportadora": "ViaLog", "uf": "SP"}
    sexta = datetime(2026, 11, 6, 10, 0, tzinfo=FUSO)
    # 3 de preparo (09, 10, 11) + 2 de transporte (12, 13)
    assert prazo_de_entrega(p, bruto, politicas(), sexta) == date(2026, 11, 13)


def test_HP_04_sem_transportadora_conhecida_nao_inventa_prazo():
    p = pedido("GBH1", marca="Kokeshi")
    assert prazo_de_entrega(p, {"transportadora": "Nova", "uf": "SP"}, politicas(), AGORA) is None


def test_HP_04_reenvio_responde_com_prazo_e_encerra_com_tag_avaria():
    base = BaseFalsa()
    base.conversa("AT1", ["O body mist chegou vazando."], order_id="GBH1")
    base.com_pedido(pedido("GBH1", valor=120.0, marca="Kokeshi"))
    base._brutos["GBH1"] = {"transportadora": "ViaLog", "uf": "SP"}
    base.com_anexo(anexo("AT1", "GBH1", captura=captura(31)))
    ferramentas = FerramentasFalsas(base)
    caso = Agente(base, ferramentas).processar("AT1")
    acoes = [r.acao for r in caso.acoes]
    assert "reenviar_produto" in acoes
    assert "05/11/2026" in caso.resposta_ao_cliente
    assert acoes[-1] == "encerrar_conversa"
    encerrar = next(p for p in ferramentas.propostas if p.ferramenta == "encerrar_conversa")
    assert "Avaria" in encerrar.motivo
    assert caso.estado == "resolvida"
