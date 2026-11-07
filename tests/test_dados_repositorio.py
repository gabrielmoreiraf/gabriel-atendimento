"""Leitura por ID devolvendo os contratos (EC-21, HP-08)."""

from datetime import date, datetime
from pathlib import Path

import pytest

from atendimento.contratos import FUSO, AcaoAnterior, Anexo, Pedido
from atendimento.dados.carga import carregar
from atendimento.dados.repositorio import Base

FIXTURES = Path(__file__).parent / "fixtures" / "dados"


@pytest.fixture
def base(tmp_path):
    caminho = tmp_path / "base.db"
    carregar(FIXTURES, caminho)
    return Base(caminho)


def test_EC_21_pedido_com_itens_e_datas(base):
    pedido = base.pedido("GBH366247")

    assert isinstance(pedido, Pedido)
    assert pedido.customer_id == "CH660017"
    assert pedido.valor == pytest.approx(162.72)
    assert pedido.status_entrega == "entregue"
    assert pedido.data_separacao == date(2026, 7, 27)
    assert pedido.data_entrega == date(2026, 7, 29)
    assert pedido.lote_produto == "LT2606-C"
    assert [i.item_id for i in pedido.itens] == ["GBH366247-1"]
    assert pedido.itens[0].sku == "YNZ-5001"


def test_EC_21_pedido_gocase_tem_texto_de_personalizacao_e_lote_vazio(base):
    pedido = base.pedido("GCH525121")

    assert pedido.lote_produto is None
    assert any(i.texto_personalizacao for i in pedido.itens)


def test_EC_21_pedido_inexistente_devolve_none(base):
    assert base.pedido("NAOEXISTE") is None


def test_EC_21_anexos_da_conversa_com_exif_em_datetime_com_fuso(base):
    anexos = base.anexos_da_conversa("AT106191")

    assert len(anexos) == 1
    anexo = anexos[0]
    assert isinstance(anexo, Anexo)
    assert anexo.anexo_id == "IMG000053"
    assert anexo.order_id == "GBH367665"
    assert anexo.exif_data_captura == datetime(2026, 8, 16, 2, 40, 13, tzinfo=FUSO)
    assert anexo.exif_software == "Editor de Fotos do Galaxy"


def test_EC_21_anexo_sem_exif_vira_none(base):
    anexo = base.anexos_da_conversa("AT104667")[0]

    assert anexo.exif_data_captura is None
    assert anexo.exif_software is None


def test_EC_21_anexos_por_hash(base):
    anexos = base.anexos_por_hash("c299e0aaf1507c96")

    assert {a.anexo_id for a in anexos} == {"IMG000053", "IMG000063"}


def test_HP_08_acoes_com_dinheiro_do_historico(base):
    acoes = base.acoes_com_dinheiro("GBH366247")

    assert acoes == [
        AcaoAnterior(
            acao_id="AC000030",
            order_id="GBH366247",
            acao="reenviar_produto",
            valor_rs=162.72,
            executado_por="atendente_04",
            aprovado_por=None,
        )
    ]


def test_HP_08_acoes_com_dinheiro_inclui_acoes_do_agente(base):
    with base.conexao:
        base.conexao.execute(
            "INSERT INTO acoes_agente VALUES ('AG000001','AT1','GBH366247','2026-11-02 08:00:00',"
            "'Gateway de pagamentos','reembolsar','50.0','agente',NULL,'EST000999')"
        )

    acoes = base.acoes_com_dinheiro("GBH366247")

    assert [a.acao for a in acoes] == ["reenviar_produto", "reembolsar"]
    assert acoes[-1].valor_rs == 50.0


def test_EC_21_reenvios_do_cliente(base):
    assert base.reenvios_do_cliente("CH660017") == 1
    assert base.reenvios_do_cliente("CH000000") == 0


def test_EC_19_reenvios_do_cliente_ignora_troca_e_nova_producao(tmp_path):
    """SPEC Q15 / EC-19: conta só `trocas_reenvios.tipo == "reenvio"`."""
    import csv
    import shutil

    origem = tmp_path / "docs"
    shutil.copytree(FIXTURES, origem)
    arquivo = origem / "trocas_reenvios.csv"
    with open(arquivo, encoding="utf-8", newline="") as f:
        colunas = next(csv.reader(f))
    with open(arquivo, "a", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=colunas)
        for n, tipo in enumerate(("troca", "nova_producao", "reenvio"), start=1):
            escritor.writerow(
                {c: "" for c in colunas}
                | {
                    "solicitacao_id": f"OMS9{n:05d}",
                    "acao_id": f"AC9{n:05d}",
                    "customer_id": "CH660017",
                    "order_id_original": "GBH366247",
                    "tipo": tipo,
                }
            )
    caminho = tmp_path / "base.db"
    carregar(origem, caminho)

    # fixture original: 1 reenvio; acrescentadas: 1 troca, 1 nova_producao, 1 reenvio
    assert Base(caminho).reenvios_do_cliente("CH660017") == 2


def test_EC_21_fila_e_mensagens(base):
    fila = base.fila()
    assert [c["conversation_id"] for c in fila] == ["AT116160", "AT116171", "AT116473"]

    mensagens = base.mensagens("AT116160")
    assert mensagens[0]["autor"] == "cliente"
    assert "GBH473217" in mensagens[0]["texto"]
    assert [m["timestamp"] for m in mensagens] == sorted(m["timestamp"] for m in mensagens)


def test_EC_21_cliente_vem_com_dados_pessoais_mascarados(base):
    cliente = base.cliente("CH660017")

    assert cliente["customer_id"] == "CH660017"
    assert cliente["cpf"].startswith("***.***.***-")
    assert cliente["telefone"].startswith("(**) *****-")
    assert base.cliente("CH000000") is None


def test_EC_21_equipe_e_politicas(base):
    equipe = base.equipe()
    assert {p["colaborador_id"] for p in equipe} >= {"supervisor_01", "analista_01"}

    politicas = base.politicas()
    assert politicas["limites_por_papel.atendente.reembolso_max_rs"] == "100.0"
    assert politicas["limites_por_papel.atendente.reenvio_ou_reimpressao_max_rs"] == "200.0"
