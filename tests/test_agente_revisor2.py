"""Segunda rodada do revisor: HP-09 (rastreio consultado), EC-03 (coleta reversa),
EC-22 (supervisor do atendente e fila até o turno), HP-08 (textos públicos e prazos)."""

from datetime import date, datetime

from fixtures.agente.falsos import BaseFalsa, FerramentasFalsas, anexo, captura, pedido

from atendimento.agente.caso import COM_DINHEIRO, Agente
from atendimento.contratos import FUSO

INTERNO = ("categorias.", "limites_por_papel", "reclamacao_suspeita.", "exige_foto")


def _proposta(ferramentas, nome):
    return next(p for p in ferramentas.propostas if p.ferramenta == nome)


# (2) HP-09: rastreio de verdade
def test_HP_09_rastreio_consulta_o_portal_e_informa_status_transportadora_e_previsao():
    base = BaseFalsa()
    base.conversa("AT1", ["Cadê meu pedido? O rastreio não anda."], order_id="GBH1")
    base.com_pedido(pedido("GBH1", valor=80.0, status_entrega="em_transito", entrega=None))
    base._brutos["GBH1"] = {"transportadora": "Expressa Já", "data_prometida": "2026-11-04"}
    ferramentas = FerramentasFalsas(base)
    ferramentas.rastreios["GBH1"] = [
        {
            "portal": "Expressa Já",
            "status": "aguardando transferência",
            "local": "CD Caucaia (CE)",
            "data_hora_evento": "2026-10-31 09:12:00",
            "previsao_entrega": "",
        }
    ]
    caso = Agente(base, ferramentas).processar("AT1")
    assert ferramentas.consultas_rastreio == ["GBH1"]
    motivo = _proposta(ferramentas, "informar_status").motivo
    for trecho in ("aguardando transferência", "Expressa Já", "04/11/2026", "31/10/2026"):
        assert trecho in motivo
        assert trecho in caso.resposta_ao_cliente


def test_HP_09_rastreio_sem_eventos_nao_finge_que_consultou():
    base = BaseFalsa()
    base.conversa("AT1", ["Cadê meu pedido? O rastreio não anda."], order_id="GBH1")
    base.com_pedido(pedido("GBH1", valor=80.0, status_entrega="em_transito", entrega=None))
    base._brutos["GBH1"] = {"transportadora": "ViaLog", "data_prometida": "2026-11-05"}
    ferramentas = FerramentasFalsas(base)
    caso = Agente(base, ferramentas).processar("AT1")
    assert ferramentas.consultas_rastreio == ["GBH1"]
    assert "ViaLog" in caso.resposta_ao_cliente
    assert "05/11/2026" in caso.resposta_ao_cliente
    assert "Consultamos o rastreio" not in caso.resposta_ao_cliente


# (3) EC-03: coleta reversa
def _arrependimento(valor):
    base = BaseFalsa()
    base.conversa("AT1", ["Recebi o kit mas não gostei, quero devolver."], order_id="GBH1")
    base.com_pedido(pedido("GBH1", valor=valor, entrega=date(2026, 10, 30)))
    ferramentas = FerramentasFalsas(base)
    return base, ferramentas, Agente(base, ferramentas)


def test_EC_03_reembolso_por_arrependimento_aciona_logistica_para_coleta_reversa():
    _, ferramentas, agente = _arrependimento(60.0)
    caso = agente.processar("AT1")
    assert "reembolsar" in [r.acao for r in caso.acoes]
    assert ("acionar_pessoa", "logistica") in ferramentas.areas
    assert "coleta" in _proposta(ferramentas, "acionar_pessoa").motivo


def test_EC_03_coleta_reversa_tambem_depois_da_aprovacao():
    _, ferramentas, agente = _arrependimento(150.0)
    caso = agente.processar("AT1")
    assert ("acionar_pessoa", "logistica") not in ferramentas.areas
    agente.aprovar(caso.aprovacao_ids[0], "supervisor_01")
    assert ("acionar_pessoa", "logistica") in ferramentas.areas


# (4) EC-22
def _acima_da_alcada(agora=None, atendente_id="atendente_01"):
    base = BaseFalsa()
    base.conversa("AT1", ["O pote chegou amassado."], order_id="GBH2", atendente_id=atendente_id)
    base.com_pedido(pedido("GBH2", valor=260.0))
    base.com_anexo(anexo("AT1", "GBH2", captura=captura(31)))
    kw = {"agora": agora} if agora else {}
    agente = Agente(base, FerramentasFalsas(base), **kw)
    return agente, agente.processar("AT1")


def test_EC_22_aprovacao_vai_para_o_supervisor_do_atendente():
    agente, _ = _acima_da_alcada()
    pedido_canal = next(m for m in agente.canal if m["tipo"] == "aprovacao")
    assert pedido_canal["para"] == "supervisor_02"


def test_EC_22_sem_supervisor_no_turno_cliente_recebe_o_prazo():
    agente, caso = _acima_da_alcada(agora=datetime(2026, 11, 2, 21, 0, tzinfo=FUSO))
    assert caso.estado == "aguardando_aprovacao"
    assert "08:00" in caso.resposta_ao_cliente


# (5) HP-08
def test_HP_08_prazo_da_analise_vem_de_politicas():
    base = BaseFalsa()
    base.conversa("AT1", ["O pote chegou amassado e vazou."], order_id="GBH3")
    base.com_pedido(pedido("GBH3", valor=150.0))
    base.com_anexo(anexo("AT1", "GBH3", "IMG1", hash_="hrep", captura=captura(31)))
    base.com_anexo(anexo("AT9", "GBH999999", "IMG9", hash_="hrep", captura=captura(10)))
    agente = Agente(base, FerramentasFalsas(base))
    agente.politicas["reclamacao_suspeita.prazo_decisao_horas"] = "12"
    caso = agente.processar("AT1")
    assert caso.estado == "suspeita"
    assert "12 horas" in caso.resposta_ao_cliente


def test_HP_08_textos_das_ferramentas_ao_cliente_sao_publicos_e_nao_vazios():
    casos = [
        (["Chegou vazando."], pedido("GBH4", valor=100.0, entrega=date(2026, 10, 1)), True),
        (["A capinha veio riscada."], pedido("GBH4", valor=80.0), False),
        (["fiquei com o rosto inchado"], pedido("GBH4", valor=80.0), False),
    ]
    for textos, p, com_foto in casos:
        base = BaseFalsa()
        base.conversa("AT1", textos, order_id="GBH4")
        base.com_pedido(p)
        if com_foto:
            base.com_anexo(anexo("AT1", "GBH4", captura=captura(2)))
        ferramentas = FerramentasFalsas(base)
        Agente(base, ferramentas).processar("AT1")
        for proposta in ferramentas.propostas:
            if proposta.ferramenta in (
                "negar_por_politica",
                "solicitar_foto",
                "orientar_suspensao_uso",
            ):
                assert proposta.motivo.strip(), proposta.ferramenta
                assert not any(i in proposta.motivo for i in INTERNO), proposta.motivo


def test_HP_08_cancelar_pedido_e_acao_com_dinheiro():
    assert "cancelar_pedido" in COM_DINHEIRO
