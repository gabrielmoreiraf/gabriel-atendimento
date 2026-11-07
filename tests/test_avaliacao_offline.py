"""Avaliação offline contra o histórico (HG-18). Fixtures mínimas montadas no próprio teste."""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

import pytest

from atendimento.avaliacao import (
    Historico,
    acerto_categoria,
    avaliar_acoes,
    avaliar_anexos,
    carregar_historico,
    casos_m11,
    escalacoes_corretas,
    gerar_relatorio,
    mapa_tag_categoria,
    piores_categorias,
    tag_da_categoria,
)
from atendimento.contratos import FUSO, Anexo, Item, Pedido, Resultado

POLITICAS = {
    "limites_por_papel.atendente.reembolso_max_rs": "100.0",
    "limites_por_papel.atendente.reenvio_ou_reimpressao_max_rs": "200.0",
    "limites_por_papel.atendente.troca_max_rs": "200.0",
    "categorias.avaria_vazamento.tag_equivalente": "Avaria",
    "categorias.avaria_vazamento.prazo_dias_corridos_do_recebimento": "7",
    "categorias.troca_fragrancia.tag_equivalente": "Troca",
    "categorias.troca_fragrancia.max_trocas_por_pedido": "1",
    "categorias.cobranca_duplicada.tag_equivalente": "Financeiro",
    "categorias.pagamento_pendente.tag_equivalente": "Financeiro",
    "categorias.erro_personalizacao.tag_equivalente": "",
    "horario_atendimento_humano.inicio": "08:00",
}
EQUIPE = [
    {"colaborador_id": "atendente_01", "cargo": "atendente", "turno": "08h-20h", "status": "ativo"},
    {
        "colaborador_id": "supervisor_01",
        "cargo": "supervisor",
        "turno": "08h-20h",
        "status": "ativo",
    },
]


def _pedido(order_id="P1", valor=300.0, entrega=date(2026, 9, 1), customer_id="C1"):
    return Pedido(
        order_id=order_id,
        customer_id=customer_id,
        marca="Gocase",
        valor=valor,
        status_entrega="entregue",
        data_separacao=date(2026, 8, 28),
        data_entrega=entrega,
        lote_produto=None,
        itens=(Item("I1", "SKU", "Capinha", "venda", valor, None),),
    )


def _acao(acao_id, acao, valor, conv="AT1", order="P1", data="2026-09-02 10:00:00", aprovado=""):
    return {
        "acao_id": acao_id,
        "conversation_id": conv,
        "order_id": order,
        "data_hora": data,
        "acao": acao,
        "valor_rs": str(valor),
        "executado_por": "atendente_01",
        "aprovado_por": aprovado,
    }


CONVERSAS = {
    "AT1": {
        "conversation_id": "AT1",
        "customer_id": "C1",
        "tag_agente": "Avaria",
        "data_abertura": "2026-09-02 09:00:00",
    },
    "AT2": {
        "conversation_id": "AT2",
        "customer_id": "C1",
        "tag_agente": "Avaria",
        "data_abertura": "2026-09-03 09:00:00",
    },
    "AT3": {
        "conversation_id": "AT3",
        "customer_id": "C1",
        "tag_agente": "Financeiro",
        "data_abertura": "2026-09-03 09:00:00",
    },
}


def test_HG_18_tag_do_agente_vira_categoria_da_politica():
    mapa = mapa_tag_categoria(POLITICAS)
    assert mapa["Avaria"] == "avaria_vazamento"
    assert mapa["Financeiro"] == "cobranca_duplicada"  # primeira categoria com a tag
    assert "" not in mapa


def test_HG_18_acao_dentro_da_alcada_nao_diverge():
    linhas = avaliar_acoes(
        [_acao("A1", "reenviar_produto", 150)],
        pedidos={"P1": _pedido()},
        conversas=CONVERSAS,
        politicas=POLITICAS,
        equipe=EQUIPE,
    )
    assert linhas[0].decisao.resultado is Resultado.EXECUTAR
    assert linhas[0].divergencia is None


def test_HG_18_soma_no_pedido_acima_da_alcada_diverge_como_alcada_acumulada():
    linhas = avaliar_acoes(
        [
            _acao("A1", "reenviar_produto", 150, conv="AT1"),
            _acao("A2", "reenviar_produto", 150, conv="AT2", data="2026-09-03 10:00:00"),
        ],
        pedidos={"P1": _pedido()},
        conversas=CONVERSAS,
        politicas=POLITICAS,
        equipe=EQUIPE,
    )
    assert [linha.divergencia for linha in linhas] == [None, "alcada_acumulada"]
    assert linhas[1].decisao.resultado is Resultado.PEDIR_APROVACAO


def test_HG_18_acao_isolada_acima_do_limite_sem_aprovacao_diverge_como_alcada():
    linhas = avaliar_acoes(
        [_acao("A1", "reembolsar", 150, conv="AT3")],
        pedidos={"P1": _pedido()},
        conversas=CONVERSAS,
        politicas=POLITICAS,
        equipe=EQUIPE,
    )
    assert linhas[0].divergencia == "alcada"


def test_HG_18_acao_aprovada_por_supervisor_nao_diverge():
    linhas = avaliar_acoes(
        [_acao("A1", "reembolsar", 150, conv="AT3", aprovado="supervisor_01")],
        pedidos={"P1": _pedido()},
        conversas=CONVERSAS,
        politicas=POLITICAS,
        equipe=EQUIPE,
    )
    assert linhas[0].divergencia is None


def test_HG_18_avaria_fora_do_prazo_diverge_como_prazo_usando_a_data_da_acao():
    linhas = avaliar_acoes(
        [_acao("A1", "reenviar_produto", 50, data="2026-09-20 10:00:00")],
        pedidos={"P1": _pedido(entrega=date(2026, 9, 1))},
        conversas=CONVERSAS,
        politicas=POLITICAS,
        equipe=EQUIPE,
    )
    assert linhas[0].decisao.resultado is Resultado.NEGAR
    assert linhas[0].divergencia == "prazo"


def test_HG_18_casos_m11_mesma_acao_em_conversas_diferentes():
    acoes = [
        _acao("A1", "reembolsar", 60, conv="AT1"),
        _acao("A2", "reembolsar", 60, conv="AT2"),
        _acao("A3", "reenviar_produto", 150, conv="AT1", order="P2"),
        _acao("A4", "reenviar_produto", 150, conv="AT1", order="P2"),  # mesma conversa
        _acao("A5", "reembolsar", 60, conv="AT1", order="P3"),
        _acao("A6", "reembolsar", 60, conv="AT2", order="P3", aprovado="supervisor_01"),
    ]
    assert casos_m11(acoes, POLITICAS) == [("P1", "reembolsar")]


def _anexo(anexo_id, conv, hash_, order="P1"):
    return Anexo(anexo_id, conv, order, hash_, None, None, "Capinha quebrada")


def test_HG_18_anexo_suspeito_que_recebeu_reenvio_conta_custo_evitado():
    pedidos = {"P1": _pedido(valor=300.0), "P2": _pedido(order_id="P2", valor=80.0)}
    anexos = [_anexo("IMG1", "AT1", "abc", "P1"), _anexo("IMG2", "AT2", "abc", "P2")]
    conversas = {
        "AT1": {**CONVERSAS["AT1"], "order_id": "P1"},
        "AT2": {**CONVERSAS["AT2"], "order_id": "P2"},
    }
    acoes = [_acao("A1", "reenviar_produto", 120, conv="AT2"), _acao("A2", "consultar_pedido", "")]
    # Só conta o que já existia quando a foto chegou: IMG2 repete o hash da IMG1, anterior.
    enviado_em = {
        "IMG1": datetime(2026, 9, 2, 9, 0, tzinfo=FUSO),
        "IMG2": datetime(2026, 9, 3, 9, 0, tzinfo=FUSO),
    }
    linhas = avaliar_anexos(
        anexos,
        pedidos=pedidos,
        conversas=conversas,
        acoes=acoes,
        trocas_reenvios=[],
        enviado_em=enviado_em,
    )
    por_conv = {linha.conversation_id: linha for linha in linhas}
    assert por_conv["AT1"].veredicto.suspeita is False
    assert por_conv["AT2"].veredicto.suspeita is True
    assert por_conv["AT2"].acoes_com_dinheiro == ("reenviar_produto",)
    assert por_conv["AT2"].custo_evitado_rs == pytest.approx(36.0)  # 80 × 0,45
    assert por_conv["AT1"].custo_evitado_rs == 0.0


def test_HG_18_carrega_csv_e_gera_relatorio_com_consultas(tmp_path: Path):
    def escrever(nome, linhas):
        with open(tmp_path / f"{nome}.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(linhas[0]))
            w.writeheader()
            w.writerows(linhas)

    escrever(
        "politicas",
        [
            {"secao": k.split(".", 1)[0], "regra": k.split(".", 1)[1], "valor": v}
            for k, v in POLITICAS.items()
        ],
    )
    escrever("equipe_atendimento", [{**p, "supervisor_id": ""} for p in EQUIPE])
    escrever(
        "pedidos",
        [
            {
                "order_id": "P1",
                "customer_id": "C1",
                "marca": "Gocase",
                "valor": "300.00",
                "status_entrega": "entregue",
                "data_separacao": "2026-08-28 10:00:00",
                "data_entrega": "2026-09-01",
                "lote_produto": "",
            }
        ],
    )
    escrever(
        "itens_pedido",
        [
            {
                "item_id": "P1-1",
                "order_id": "P1",
                "linha": "1",
                "sku": "S",
                "descricao": "Capinha",
                "tipo_item": "venda",
                "valor_total": "300.00",
                "texto_personalizacao": "",
            }
        ],
    )
    escrever("historico_conversas", [{**CONVERSAS["AT1"], "order_id": "P1"}])
    escrever("acoes_executadas_sistemas", [_acao("A1", "reenviar_produto", 150)])
    escrever(
        "anexos_conversas",
        [
            {
                "anexo_id": "IMG1",
                "conversation_id": "AT1",
                "order_id": "P1",
                "hash_perceptual": "abc",
                "exif_data_captura": "",
                "exif_software": "",
                "descricao_visual": "Capinha quebrada",
            }
        ],
    )
    escrever(
        "trocas_reenvios",
        [{"customer_id": "C1", "data_solicitacao": "2026-08-01 10:00:00", "tipo": "reenvio"}],
    )

    historico = carregar_historico(tmp_path)
    assert isinstance(historico, Historico)
    assert historico.pedidos["P1"].data_entrega == date(2026, 9, 1)
    relatorio = gerar_relatorio(historico)
    assert "HG-18" in relatorio
    assert "acoes_executadas_sistemas.csv" in relatorio
    assert "| reenviar_produto |" in relatorio


@pytest.mark.integracao
def test_HG_18_base_real_reproduz_os_64_casos_m11_e_o_motor_pega_todos():
    pasta = Path(__file__).resolve().parents[1] / "docs"
    historico = carregar_historico(pasta)
    casos = casos_m11(historico.acoes, historico.politicas)
    assert len(casos) == 64
    linhas = avaliar_acoes(
        historico.acoes,
        pedidos=historico.pedidos,
        conversas=historico.conversas,
        politicas=historico.politicas,
        equipe=historico.equipe,
    )
    pegos = {
        (linha.order_id, linha.acao)
        for linha in linhas
        if linha.decisao.resultado is not Resultado.EXECUTAR
    }
    assert set(casos) <= pegos


def test_HG_18_data_hora_da_acao_e_local():
    linhas = avaliar_acoes(
        [_acao("A1", "reenviar_produto", 50)],
        pedidos={"P1": _pedido()},
        conversas=CONVERSAS,
        politicas=POLITICAS,
        equipe=EQUIPE,
    )
    assert linhas[0].data_hora == datetime(2026, 9, 2, 10, 0, tzinfo=FUSO)


def test_HG_18_acao_antes_do_recebimento_nao_conta_como_fora_do_prazo():
    linhas = avaliar_acoes(
        [
            _acao("A1", "reenviar_produto", 50, data="2026-08-30 10:00:00"),
            _acao("A2", "reenviar_produto", 50, order="P2"),
        ],
        pedidos={"P1": _pedido(entrega=date(2026, 9, 1)), "P2": _pedido("P2", entrega=None)},
        conversas=CONVERSAS,
        politicas=POLITICAS,
        equipe=EQUIPE,
    )
    assert [linha.divergencia for linha in linhas] == [
        "antes_do_recebimento",
        "antes_do_recebimento",
    ]


def test_HG_18_rotula_acao_fora_das_permitidas_e_sem_pedido():
    politicas = {**POLITICAS, "categorias.avaria_vazamento.acoes_permitidas": "reenviar_produto"}
    linhas = avaliar_acoes(
        [
            _acao("A1", "reembolsar", 50),
            _acao("A2", "reenviar_produto", 50, order="SEM"),
        ],
        pedidos={"P1": _pedido()},
        conversas=CONVERSAS,
        politicas=politicas,
        equipe=EQUIPE,
    )
    assert [linha.divergencia for linha in linhas] == ["acao_nao_permitida", "sem_pedido"]


@pytest.mark.parametrize(
    ("tipo", "conta"), [("reenvio", True), ("troca", False), ("nova_producao", False)]
)
def test_EC_19_so_reenvios_contam_no_historico_do_cliente(tipo, conta):
    trocas = [
        {"customer_id": "C1", "data_solicitacao": f"2026-08-0{d} 10:00:00", "tipo": tipo}
        for d in (1, 2, 3)
    ]
    linhas = avaliar_anexos(
        [_anexo("IMG1", "AT1", "abc")],
        pedidos={"P1": _pedido()},
        conversas={"AT1": {**CONVERSAS["AT1"], "order_id": "P1"}},
        acoes=[],
        trocas_reenvios=trocas,
    )
    tipos = {s.tipo.value for s in linhas[0].veredicto.sinais}
    assert ("reenvios_anteriores" in tipos) is conta


# ---------- HG-18: acerto de categoria do leitor contra a tag humana ----------

POLITICAS_TAGS = {
    "categorias.atraso_entrega.tag_equivalente": "Atraso",
    "categorias.onde_esta_pedido.tag_equivalente": "Rastreio",
    "categorias.avaria_vazamento.tag_equivalente": "Avaria",
    "categorias.erro_personalizacao.tag_equivalente": "",
    "categorias.cobranca_duplicada.tag_equivalente": "Financeiro",
}


def test_HG_18_categoria_do_leitor_vira_tag_da_politica():
    assert tag_da_categoria("atraso", POLITICAS_TAGS) == "Atraso"
    assert tag_da_categoria("rastreio", POLITICAS_TAGS) == "Rastreio"
    assert tag_da_categoria("avaria_vazamento", POLITICAS_TAGS) == "Avaria"
    # sem tag_equivalente na política: a tag humana usada é "Reclamação produto"
    assert tag_da_categoria("erro_personalizacao", POLITICAS_TAGS) == "Reclamação produto"
    assert tag_da_categoria("outros", POLITICAS_TAGS) == "Outros"


def test_HG_18_acerto_de_categoria_compara_com_tag_e_separa_sem_interacao():
    conversas = {
        "A1": {"conversation_id": "A1", "tag_agente": "Atraso"},
        "A2": {"conversation_id": "A2", "tag_agente": "Avaria"},
        "A3": {"conversation_id": "A3", "tag_agente": "Rastreio"},
    }
    mensagens = {
        "A1": ["Meu pedido está atrasado, já passou do prazo"],
        "A2": ["Meu pedido está atrasado, já passou do prazo"],
        # A3 sem mensagem do cliente
    }
    linhas = acerto_categoria(conversas, mensagens, POLITICAS_TAGS)
    por_id = {linha.conversation_id: linha for linha in linhas}
    assert por_id["A1"].acertou is True
    assert por_id["A2"].acertou is False
    assert por_id["A2"].tag_prevista == "Atraso"
    assert por_id["A3"].categoria == "sem_interacao"
    assert por_id["A3"].acertou is None


def _linha_cat(cid, tag, acertou):
    from atendimento.avaliacao.categoria import LinhaCategoria

    return LinhaCategoria(cid, tag, "x", None if acertou is None else "y", acertou)


def test_HG_18_piores_categorias_sao_calculadas_pelos_numeros():
    linhas = [
        _linha_cat("1", "A", True),
        _linha_cat("2", "A", True),
        _linha_cat("3", "B", False),
        _linha_cat("4", "B", True),
        _linha_cat("5", "C", False),
        _linha_cat("6", "D", True),
        _linha_cat("7", "E", None),  # sem interação: fora da conta
    ]
    piores = piores_categorias(linhas, quantas=3)
    assert [(p[0], p[1], p[2]) for p in piores] == [("C", 1, 0), ("B", 2, 1), ("A", 2, 2)]


def test_HG_18_escalacoes_corretas_com_criterio_explicito():
    sensiveis = {"AT1", "AT2", "AT3"}  # o leitor marcou reação adversa
    acoes = [
        {"conversation_id": "AT1", "acao": "registrar_cosmetovigilancia", "aprovado_por": ""},
        {"conversation_id": "AT2", "acao": "reembolsar", "aprovado_por": "supervisor_01"},
        {"conversation_id": "AT3", "acao": "trocar_produto", "aprovado_por": ""},
        {"conversation_id": "AT4", "acao": "registrar_cosmetovigilancia", "aprovado_por": ""},
    ]
    m = escalacoes_corretas(sensiveis, acoes)
    assert m["sensiveis_leitor"] == 3
    assert m["com_escalacao_humana"] == 2  # AT1 (cosmetovigilância) e AT2 (aprovação)
    assert m["cosmetovigilancia_humana"] == 2
    assert m["cosmetovigilancia_vista_pelo_leitor"] == 1  # AT4 o leitor não marcou


def test_HG_18_relatorio_nao_tem_texto_fixo_de_categoria_faltando():
    from atendimento.avaliacao import relatorio

    fonte = Path(relatorio.__file__).read_text(encoding="utf-8")
    assert "não reconhece troca de fragrância" not in fonte
