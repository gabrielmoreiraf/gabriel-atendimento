"""Motor de políticas (W2). Cada teste leva o ID do cenário de REQUISITOS.md."""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from atendimento.contratos import (
    AGORA,
    FUSO,
    AcaoAnterior,
    AcaoProposta,
    Papel,
    Pedido,
    Resultado,
    Sinal,
    TipoSinal,
    VeredictoEvidencia,
)
from atendimento.politicas import decidir, dentro_da_janela, supervisor_no_turno

FIXTURES = Path(__file__).parent / "fixtures" / "politicas"


def _carregar_politicas() -> dict[str, str]:
    with open(FIXTURES / "politicas.csv", encoding="utf-8", newline="") as f:
        return {f"{x['secao']}.{x['regra']}": x["valor"] for x in csv.DictReader(f)}


def _carregar_equipe() -> list[dict]:
    with open(FIXTURES / "equipe.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


POLITICAS = _carregar_politicas()
EQUIPE = _carregar_equipe()


def _pedido(*, entrega_ha_dias: int | None = 2, separado: bool = True) -> Pedido:
    return Pedido(
        order_id="GBH1",
        customer_id="C1",
        marca="GoBeauté",
        valor=300.0,
        status_entrega="entregue" if entrega_ha_dias is not None else "em_transito",
        data_separacao=date(2026, 10, 20) if separado else None,
        data_entrega=(AGORA.date() - timedelta(days=entrega_ha_dias))
        if entrega_ha_dias is not None
        else None,
        lote_produto="L1",
    )


def _acao(ferramenta: str, valor: float, **kw) -> AcaoProposta:
    return AcaoProposta(
        ferramenta=ferramenta,
        papel=kw.pop("papel", Papel.ATENDENTE),
        executado_por=kw.pop("executado_por", "agente"),
        order_id="GBH1",
        valor_rs=valor,
        **kw,
    )


def _anterior(acao: str, valor: float, aprovado_por: str | None = None, order_id="GBH1"):
    return AcaoAnterior(
        acao_id="A1",
        order_id=order_id,
        acao=acao,
        valor_rs=valor,
        executado_por="atendente_03",
        aprovado_por=aprovado_por,
    )


def _decidir(acao, *, pedido=None, anteriores=(), agora=AGORA, **kw):
    return decidir(
        acao,
        pedido=pedido if pedido is not None else _pedido(),
        acoes_anteriores=list(anteriores),
        politicas=POLITICAS,
        equipe=EQUIPE,
        agora=agora,
        **kw,
    )


# ---------- EC-01: reembolso ----------


def test_EC_01_reembolso_de_100_executa():
    d = _decidir(_acao("reembolsar", 100.00))
    assert d.resultado is Resultado.EXECUTAR
    assert d.regra == "limites_por_papel.atendente.reembolso_max_rs"


def test_EC_01_reembolso_de_100_01_pede_aprovacao_com_aprovador():
    d = _decidir(_acao("reembolsar", 100.01))
    assert d.resultado is Resultado.PEDIR_APROVACAO
    assert d.regra == "limites_por_papel.atendente.reembolso_max_rs"
    assert d.aprovador_sugerido in {"supervisor_01", "supervisor_02", "supervisor_03"}


# ---------- EC-02: reenvio, reimpressão, troca ----------


@pytest.mark.parametrize(
    ("ferramenta", "regra"),
    [
        ("reenviar_produto", "limites_por_papel.atendente.reenvio_ou_reimpressao_max_rs"),
        ("reimprimir_personalizacao", "limites_por_papel.atendente.reenvio_ou_reimpressao_max_rs"),
        ("trocar_produto", "limites_por_papel.atendente.troca_max_rs"),
    ],
)
def test_EC_02_limite_de_200(ferramenta, regra):
    assert _decidir(_acao(ferramenta, 200.00)).resultado is Resultado.EXECUTAR
    d = _decidir(_acao(ferramenta, 200.01))
    assert d.resultado is Resultado.PEDIR_APROVACAO
    assert d.regra == regra
    assert d.aprovador_sugerido is not None


# ---------- HG-22 / Q10: alçada acumulada por pedido ----------


def test_HG_22_reembolso_acumulado_passa_do_limite_pede_aprovacao():
    d = _decidir(_acao("reembolsar", 50.0), anteriores=[_anterior("reembolsar", 60.0)])
    assert d.resultado is Resultado.PEDIR_APROVACAO
    assert d.regra == "limites_por_papel.atendente.reembolso_max_rs"
    assert d.detalhes["acumulado_rs"] == 60.0


def test_HG_22_reenvio_e_reimpressao_somam_juntos():
    d = _decidir(
        _acao("reimprimir_personalizacao", 120.0),
        anteriores=[_anterior("reenviar_produto", 90.0)],
    )
    assert d.resultado is Resultado.PEDIR_APROVACAO


def test_HG_22_acao_anterior_aprovada_tambem_conta_no_acumulado():
    """SPEC.md Q10 (revisão do `revisor`): a alçada soma TODAS as ações com dinheiro do
    pedido no grupo, aprovadas ou não; uma aprovação cobre só a ação aprovada."""
    d = _decidir(
        _acao("reembolsar", 50.0),
        anteriores=[_anterior("reembolsar", 300.0, aprovado_por="supervisor_02")],
    )
    assert d.resultado is Resultado.PEDIR_APROVACAO
    assert d.detalhes["acumulado_rs"] == 300.0


def test_HG_22_acoes_de_outro_pedido_ou_outro_grupo_nao_contam():
    d = _decidir(
        _acao("reembolsar", 90.0),
        anteriores=[
            _anterior("reembolsar", 90.0, order_id="OUTRO"),
            _anterior("reenviar_produto", 150.0),
        ],
    )
    assert d.resultado is Resultado.EXECUTAR


def test_HG_22_segunda_troca_no_mesmo_pedido_e_negada():
    d = _decidir(_acao("trocar_produto", 80.0), anteriores=[_anterior("trocar_produto", 80.0)])
    assert d.resultado is Resultado.NEGAR
    assert d.regra == "categorias.troca_fragrancia.max_trocas_por_pedido"


# ---------- HG-05: aprovação válida ----------


def test_HG_05_acima_do_limite_com_aprovacao_valida_executa():
    d = _decidir(_acao("reembolsar", 150.0, aprovacao_id="APR1", aprovado_por="supervisor_02"))
    assert d.resultado is Resultado.EXECUTAR
    assert d.regra == "limites_por_papel.atendente.reembolso_max_rs"


def test_HG_05_acima_do_limite_sem_aprovacao_id_pede_aprovacao():
    d = _decidir(_acao("reembolsar", 150.0, aprovado_por="supervisor_02"))
    assert d.resultado is Resultado.PEDIR_APROVACAO


def test_HG_05_aprovacao_de_quem_nao_e_supervisor_nao_vale():
    d = _decidir(_acao("reembolsar", 150.0, aprovacao_id="APR1", aprovado_por="atendente_01"))
    assert d.resultado is Resultado.PEDIR_APROVACAO


# ---------- HG-03: autoaprovação ----------


def test_HG_03_supervisor_nao_aprova_a_propria_acao():
    d = _decidir(
        _acao(
            "reembolsar",
            150.0,
            papel=Papel.SUPERVISOR,
            executado_por="supervisor_01",
            aprovacao_id="APR1",
            aprovado_por="supervisor_01",
        )
    )
    assert d.resultado is Resultado.BLOQUEAR
    assert d.regra == "limites_por_papel.supervisor.nao_aprova_a_propria_acao"


# ---------- HG-04: quem sinaliza não decide ----------


def test_HG_04_quem_sinalizou_nao_decide_a_suspeita():
    d = _decidir(
        _acao("decidir_suspeita", 0.0, executado_por="atendente_03"),
        sinalizado_por="atendente_03",
    )
    assert d.resultado is Resultado.BLOQUEAR
    assert d.regra == "reclamacao_suspeita.quem_decide"


def test_HG_04_quem_sinalizou_nao_aprova_a_acao():
    d = _decidir(
        _acao("reembolsar", 150.0, aprovacao_id="APR1", aprovado_por="supervisor_02"),
        sinalizado_por="supervisor_02",
    )
    assert d.resultado is Resultado.BLOQUEAR


def test_HG_04_atendente_nao_decide_suspeita_por_papel():
    d = _decidir(_acao("decidir_suspeita", 0.0, executado_por="atendente_01"))
    assert d.resultado is Resultado.BLOQUEAR
    assert d.regra == "reclamacao_suspeita.quem_decide"


# ---------- EC-03: janela de 7 dias corridos ----------


@pytest.mark.parametrize(
    ("ferramenta", "categoria"),
    [
        ("reenviar_produto", "avaria_vazamento"),
        ("reenviar_produto", "avaria"),
        ("reenviar_produto", "item_faltante"),
        ("reimprimir_personalizacao", "erro_personalizacao"),
        ("reembolsar", "arrependimento_cancelamento"),
    ],
)
def test_EC_03_dia_7_dentro_dia_8_negado(ferramenta, categoria):
    acao = _acao(ferramenta, 80.0, categoria=categoria)
    dentro = _decidir(acao, pedido=_pedido(entrega_ha_dias=7))
    assert dentro.resultado is Resultado.EXECUTAR
    if categoria == "arrependimento_cancelamento":
        # Q18: a coleta reversa do arrependimento sai explícita na decisão.
        assert "coleta_reversa" in dentro.acoes_obrigatorias
        assert dentro.detalhes["coleta_reversa"] is True
    else:
        assert "coleta_reversa" not in dentro.acoes_obrigatorias
    d = _decidir(acao, pedido=_pedido(entrega_ha_dias=8))
    assert d.resultado is Resultado.NEGAR
    assert d.regra.endswith(".prazo_dias_corridos_do_recebimento")
    assert d.regra.startswith("categorias.")


def test_EC_03_arrependimento_fora_do_prazo_nega_citando_regra():
    d = _decidir(
        _acao("reembolsar", 80.0, categoria="arrependimento_cancelamento"),
        pedido=_pedido(entrega_ha_dias=8),
    )
    assert d.resultado is Resultado.NEGAR
    assert d.regra == "categorias.arrependimento_cancelamento.prazo_dias_corridos_do_recebimento"
    assert "CDC, art. 49" in d.motivo


def test_EC_03_dentro_do_prazo_ainda_respeita_alcada():
    d = _decidir(
        _acao("reenviar_produto", 250.0, categoria="avaria_vazamento"),
        pedido=_pedido(entrega_ha_dias=3),
    )
    assert d.resultado is Resultado.PEDIR_APROVACAO


def test_EC_03_dentro_da_janela_conta_dias_corridos():
    assert dentro_da_janela(date(2026, 10, 26), AGORA) is True  # 7º dia
    assert dentro_da_janela(date(2026, 10, 25), AGORA) is False  # 8º dia
    assert dentro_da_janela(None, AGORA) is False
    assert dentro_da_janela(date(2026, 10, 3), AGORA, dias=30) is True


# ---------- HG-06: reação adversa ----------


def test_HG_06_reacao_adversa_escala_com_acoes_obrigatorias():
    d = _decidir(_acao("trocar_produto", 80.0, categoria="reacao_adversa"))
    assert d.resultado is Resultado.ESCALAR
    assert d.acoes_obrigatorias == ("orientar_suspensao_uso", "registrar_cosmetovigilancia")
    assert d.regra == "categorias.reacao_adversa.acoes_obrigatorias"
    assert d.aprovador_sugerido is not None
    assert d.detalhes["prazo_registro_horas"] == 24


# ---------- HG-08: atendente não nega por suspeita ----------


def _veredicto(suspeita: bool) -> VeredictoEvidencia:
    return VeredictoEvidencia(
        suspeita=suspeita,
        sinais=(Sinal(TipoSinal.HASH_REPETIDO, "anexo igual ao de outro pedido", "AN1"),),
        custo_aceitar_falso_rs=135.0,
        custo_sinalizar_verdadeiro_rs=6.0,
        justificativa="hash repetido",
    )


def test_HG_08_suspeita_vira_sinalizacao_e_nunca_negacao():
    d = _decidir(
        _acao("reenviar_produto", 80.0, categoria="avaria_vazamento"),
        veredicto=_veredicto(True),
    )
    assert d.resultado is Resultado.SINALIZAR_SUSPEITA
    assert d.regra == "reclamacao_suspeita.atendente_e_analista"


def test_HG_08_sem_suspeita_segue_a_politica():
    d = _decidir(
        _acao("reenviar_produto", 80.0, categoria="avaria_vazamento"),
        veredicto=_veredicto(False),
    )
    assert d.resultado is Resultado.EXECUTAR


# ---------- Antes da separação ----------


@pytest.mark.parametrize(
    ("ferramenta", "regra"),
    [
        ("cancelar_pedido", "categorias.arrependimento_cancelamento.regra"),
        ("alterar_endereco", "categorias.alteracao_endereco.regra"),
    ],
)
def test_HP_cancelar_ou_alterar_so_antes_da_separacao(ferramenta, regra):
    antes = _decidir(_acao(ferramenta, 0.0), pedido=_pedido(entrega_ha_dias=None, separado=False))
    assert antes.resultado is Resultado.EXECUTAR
    depois = _decidir(_acao(ferramenta, 0.0), pedido=_pedido(entrega_ha_dias=None, separado=True))
    assert depois.resultado is Resultado.NEGAR
    assert depois.regra == regra


# ---------- EC-22: supervisor no turno ----------


def _hora(h: int, m: int = 0) -> datetime:
    return datetime(2026, 11, 2, h, m, tzinfo=FUSO)


def test_EC_22_10h_prefere_supervisor_do_atendente():
    assert supervisor_no_turno(EQUIPE, _hora(10), preferido="supervisor_03") == "supervisor_03"
    assert supervisor_no_turno(EQUIPE, _hora(10)) in {
        "supervisor_01",
        "supervisor_02",
        "supervisor_03",
    }


def test_EC_22_18h30_so_supervisor_01():
    assert supervisor_no_turno(EQUIPE, _hora(18, 30)) == "supervisor_01"
    assert supervisor_no_turno(EQUIPE, _hora(18, 30), preferido="supervisor_02") == "supervisor_01"


def test_EC_22_18h30_autor_supervisor_01_fica_sem_aprovador():
    assert supervisor_no_turno(EQUIPE, _hora(18, 30), excluir="supervisor_01") is None


def test_EC_22_21h_fora_do_horario():
    assert supervisor_no_turno(EQUIPE, _hora(21)) is None


def test_EC_22_pedido_de_aprovacao_sem_supervisor_vai_para_fila_das_8h():
    d = _decidir(
        _acao("reembolsar", 150.0, papel=Papel.SUPERVISOR, executado_por="supervisor_01"),
        agora=_hora(18, 30),
    )
    assert d.resultado is Resultado.PEDIR_APROVACAO
    assert d.aprovador_sugerido is None
    assert d.detalhes["fila_ate"] == "08:00"


# ---------- Toda decisão cita uma chave real de politicas.csv ----------


@pytest.mark.parametrize(
    ("acao", "kw"),
    [
        (_acao("reembolsar", 50.0), {}),
        (_acao("reembolsar", 150.0), {}),
        (_acao("reembolsar", 50.0, categoria="cobranca_duplicada"), {}),
        (_acao("reenviar_produto", 80.0, categoria="avaria_vazamento"), {}),
        (_acao("trocar_produto", 80.0, categoria="reacao_adversa"), {}),
        (_acao("cancelar_pedido", 0.0), {}),
        (_acao("informar_status", 0.0), {}),
        (_acao("decidir_suspeita", 0.0), {}),
        (_acao("reenviar_produto", 80.0), {"veredicto": _veredicto(True)}),
    ],
)
def test_EC_01_toda_decisao_cita_chave_de_politicas(acao, kw):
    d = _decidir(acao, **kw)
    assert d.regra in POLITICAS


# ---------- EC-25 / Q12: sem entrega registrada, escala em vez de negar ----------


@pytest.mark.parametrize(
    ("ferramenta", "categoria"),
    [
        ("reenviar_produto", "avaria_vazamento"),
        ("reenviar_produto", "item_faltante"),
        ("reimprimir_personalizacao", "erro_personalizacao"),
        ("reembolsar", "arrependimento_cancelamento"),
    ],
)
def test_EC_25_sem_entrega_registrada_escala_e_nao_nega(ferramenta, categoria):
    """Mudança de requisito pelo Q12 (REQUISITOS.md), não afrouxamento: sem `data_entrega`
    a janela do recebimento nem começou, então não há prazo vencido para negar. O caso vai
    para uma pessoa (EC-25). NEGAR por prazo continua para entrega registrada há mais de 7
    dias (test_EC_03_dia_7_dentro_dia_8_negado)."""
    d = _decidir(
        _acao(ferramenta, 50.0, categoria=categoria),
        pedido=_pedido(entrega_ha_dias=None, separado=True),
    )
    assert d.resultado is Resultado.ESCALAR
    assert d.regra == f"categorias.{categoria}.prazo_dias_corridos_do_recebimento"
    assert d.motivo == "pedido sem entrega registrada; conferir com logística"
    assert d.aprovador_sugerido is not None


def test_EC_25_entrega_registrada_depois_de_agora_tambem_escala():
    """Entrega com data posterior ao "agora" da decisão ainda não aconteceu (Q12)."""
    pedido = _pedido(entrega_ha_dias=-2)
    d = _decidir(_acao("reenviar_produto", 50.0, categoria="avaria_vazamento"), pedido=pedido)
    assert d.resultado is Resultado.ESCALAR


# ---------- Revisão do revisor: Q20, HG-03, HG-04, status ativo, ações permitidas ----------


@pytest.mark.parametrize(
    "ferramenta", ["reembolsar", "reenviar_produto", "reimprimir_personalizacao", "trocar_produto"]
)
def test_Q20_acao_com_dinheiro_sem_pedido_escala(ferramenta):
    d = decidir(
        _acao(ferramenta, 10.0),
        pedido=None,
        acoes_anteriores=[],
        politicas=POLITICAS,
        equipe=EQUIPE,
    )
    assert d.resultado is Resultado.ESCALAR
    assert d.regra in POLITICAS


def test_HG_03_autoaprovacao_sugere_outro_supervisor():
    d = _decidir(
        _acao(
            "reembolsar",
            150.0,
            papel=Papel.SUPERVISOR,
            executado_por="supervisor_01",
            aprovacao_id="APR1",
            aprovado_por="supervisor_01",
        ),
        supervisor_preferido="supervisor_01",
    )
    assert d.resultado is Resultado.BLOQUEAR
    assert d.aprovador_sugerido in {"supervisor_02", "supervisor_03"}


def test_HG_03_pedido_de_aprovacao_nunca_sugere_quem_executa():
    d = _decidir(
        _acao("reembolsar", 150.0, papel=Papel.SUPERVISOR, executado_por="supervisor_02"),
        supervisor_preferido="supervisor_02",
    )
    assert d.resultado is Resultado.PEDIR_APROVACAO
    assert d.aprovador_sugerido not in {None, "supervisor_02"}


def test_HG_04_supervisor_que_sinalizou_nao_decide_a_propria_suspeita():
    d = _decidir(
        _acao("decidir_suspeita", 0.0, papel=Papel.SUPERVISOR, executado_por="supervisor_02"),
        sinalizado_por="supervisor_02",
    )
    assert d.resultado is Resultado.BLOQUEAR
    assert d.regra == "reclamacao_suspeita.quem_decide"


def test_HG_04_outro_supervisor_decide_a_suspeita():
    d = _decidir(
        _acao("decidir_suspeita", 0.0, papel=Papel.SUPERVISOR, executado_por="supervisor_03"),
        sinalizado_por="atendente_01",
    )
    assert d.resultado is Resultado.EXECUTAR
    assert d.regra == "reclamacao_suspeita.quem_decide"


def test_HG_05_aprovacao_de_supervisor_inativo_nao_vale():
    equipe = [
        {**p, "status": "inativo"} if p["colaborador_id"] == "supervisor_02" else p for p in EQUIPE
    ]
    d = decidir(
        _acao("reembolsar", 150.0, aprovacao_id="APR1", aprovado_por="supervisor_02"),
        pedido=_pedido(),
        acoes_anteriores=[],
        politicas=POLITICAS,
        equipe=equipe,
    )
    assert d.resultado is Resultado.PEDIR_APROVACAO


def test_HG_09_ferramenta_fora_das_acoes_permitidas_da_categoria_escala():
    d = _decidir(_acao("reembolsar", 50.0, categoria="avaria_vazamento"))
    assert d.resultado is Resultado.ESCALAR
    assert d.regra == "categorias.avaria_vazamento.acoes_permitidas"
