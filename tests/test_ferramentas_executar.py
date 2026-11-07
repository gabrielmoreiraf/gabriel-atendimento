"""Ferramentas com efeito e log de ações (HG-02, HG-12, HP-08, HP-09)."""

from pathlib import Path

import pytest

from atendimento.contratos import AGORA, AcaoProposta, Papel, RegistroAcao
from atendimento.dados.carga import carregar
from atendimento.dados.repositorio import Base
from atendimento.ferramentas import (
    FerramentaDesconhecida,
    FerramentaNaoPermitida,
    Ferramentas,
)

FIXTURES = Path(__file__).parent / "fixtures" / "dados"


@pytest.fixture
def base(tmp_path):
    caminho = tmp_path / "base.db"
    carregar(FIXTURES, caminho)
    return Base(caminho)


@pytest.fixture
def ferramentas(base):
    return Ferramentas(base)


def _contar(base, tabela, where="1=1", *parametros):
    return base.conexao.execute(
        f"SELECT COUNT(*) FROM {tabela} WHERE {where}", parametros
    ).fetchone()[0]


# ---------- HG-02: papel ----------


@pytest.mark.parametrize(
    "ferramenta",
    ["aprovar_acao", "rejeitar_acao", "registrar_cosmetovigilancia", "decidir_suspeita"],
)
def test_HG_02_atendente_nao_usa_ferramenta_de_supervisor(ferramentas, base, ferramenta):
    acao = AcaoProposta(
        ferramenta=ferramenta,
        papel=Papel.ATENDENTE,
        executado_por="agente",
        conversation_id="AT116160",
        aprovacao_id="APR-000001",
    )

    with pytest.raises(FerramentaNaoPermitida):
        ferramentas.executar(acao)

    assert _contar(base, "acoes_agente") == 0
    assert _contar(base, "tentativas_bloqueadas", "ferramenta = ?", ferramenta) == 1


def test_HG_02_supervisor_nao_reembolsa(ferramentas):
    acao = AcaoProposta(
        ferramenta="reembolsar",
        papel=Papel.SUPERVISOR,
        executado_por="supervisor_01",
        order_id="GBH366247",
        valor_rs=10.0,
    )

    with pytest.raises(FerramentaNaoPermitida):
        ferramentas.executar(acao)


def test_HG_02_ferramenta_fora_do_catalogo_de_execucao(ferramentas):
    acao = AcaoProposta(ferramenta="apagar_base", papel=Papel.ATENDENTE, executado_por="agente")

    with pytest.raises(FerramentaDesconhecida):
        ferramentas.executar(acao)


# ---------- HP-08 / HP-09: executa e registra ----------


def test_HP_09_reenvio_executado_tem_referencia_e_efeito_no_oms(ferramentas, base):
    acao = AcaoProposta(
        ferramenta="reenviar_produto",
        papel=Papel.ATENDENTE,
        executado_por="agente",
        conversation_id="AT116160",
        order_id="GBH473217",
        valor_rs=102.80,
        motivo="extravio",
        categoria="atraso_entrega",
    )

    registro = ferramentas.executar(acao)

    assert isinstance(registro, RegistroAcao)
    assert registro.referencia_sistema == "OMS000017"
    assert registro.sistema == "OMS de trocas e reenvios"
    linha = base.conexao.execute(
        "SELECT * FROM trocas_reenvios WHERE solicitacao_id = ?", (registro.referencia_sistema,)
    ).fetchone()
    assert linha["order_id_original"] == "GBH473217"
    assert linha["customer_id"] == "CH761018"
    assert linha["tipo"] == "reenvio"
    assert linha["acao_id"] == registro.acao_id


def test_HP_08_registro_tem_executor_valor_aprovador_referencia_e_agora(ferramentas, base):
    acao = AcaoProposta(
        ferramenta="reembolsar",
        papel=Papel.ATENDENTE,
        executado_por="agente",
        conversation_id="AT116160",
        order_id="GBH473217",
        valor_rs=50.0,
        motivo="atraso",
        aprovado_por="supervisor_02",
    )

    registro = ferramentas.executar(acao)

    assert registro == RegistroAcao(
        acao_id="AG000001",
        conversation_id="AT116160",
        order_id="GBH473217",
        data_hora=AGORA,
        sistema="Gateway de pagamentos",
        acao="reembolsar",
        valor_rs=50.0,
        executado_por="agente",
        aprovado_por="supervisor_02",
        referencia_sistema="EST000001",
    )
    assert ferramentas.acoes_registradas() == [registro]
    estorno = base.conexao.execute("SELECT * FROM estornos").fetchone()
    assert estorno["transacao_id"] == "TRX00005360"
    assert estorno["tipo"] == "parcial"
    assert estorno["valor"] == "50.00"


def test_HP_08_acao_do_agente_entra_no_historico_de_dinheiro(ferramentas, base):
    ferramentas.executar(
        AcaoProposta(
            ferramenta="reimprimir_personalizacao",
            papel=Papel.ATENDENTE,
            executado_por="agente",
            conversation_id="AT999",
            order_id="GCH525121",
            valor_rs=72.32,
        )
    )

    acoes = base.acoes_com_dinheiro("GCH525121")

    assert [a.acao for a in acoes] == ["reimprimir_personalizacao", "reimprimir_personalizacao"]
    assert acoes[-1].executado_por == "agente"


def test_HP_09_chamado_na_transportadora_do_pedido(ferramentas, base):
    registro = ferramentas.executar(
        AcaoProposta(
            ferramenta="abrir_chamado_transportadora",
            papel=Papel.ATENDENTE,
            executado_por="agente",
            conversation_id="AT116160",
            order_id="GBH473217",
            motivo="rastreio_sem_atualizacao",
        )
    )

    assert registro.sistema == "Portal Expressa Já"
    assert registro.referencia_sistema == "EXJ-202600363"
    assert registro.valor_rs == 0.0
    assert _contar(base, "chamados_transportadora", "chamado_id = ?", "EXJ-202600363") == 1


def test_HP_09_resposta_ao_cliente_e_gravada_sem_dados_pessoais(ferramentas, base):
    registro = ferramentas.executar(
        AcaoProposta(
            ferramenta="responder_cliente",
            papel=Papel.ATENDENTE,
            executado_por="agente",
            conversation_id="AT116160",
            motivo="Confirmamos o CPF 123.456.789-10 e o telefone (85) 99876-5432.",
        )
    )

    texto = base.conexao.execute("SELECT texto FROM mensagens_enviadas").fetchone()[0]
    assert "123.456.789-10" not in texto
    assert "***.***.***-10" in texto
    assert "99876-5432" not in texto
    assert registro.sistema == "Central de atendimento"
    assert registro.referencia_sistema.startswith("MSG-")


def test_HP_08_classificacao_registrada(ferramentas, base):
    ferramentas.executar(
        AcaoProposta(
            ferramenta="classificar_conversa",
            papel=Papel.ATENDENTE,
            executado_por="agente",
            conversation_id="AT116160",
            categoria="onde_esta_pedido",
        )
    )

    linha = base.conexao.execute("SELECT * FROM classificacoes").fetchone()
    assert (linha["conversation_id"], linha["categoria"]) == ("AT116160", "onde_esta_pedido")


def test_HP_08_suspeita_registrada(ferramentas, base):
    registro = ferramentas.executar(
        AcaoProposta(
            ferramenta="sinalizar_suspeita",
            papel=Papel.ATENDENTE,
            executado_por="agente",
            conversation_id="AT106569",
            order_id="GBH367665",
            motivo="hash_repetido: IMG000063 igual a IMG000053",
        )
    )

    assert registro.referencia_sistema == "SUS-000001"
    assert _contar(base, "suspeitas", "estado = 'pendente'") == 1


# ---------- aprovação ----------


def test_HP_08_aprovacao_solicitada_aprovada_e_usada_no_reenvio(ferramentas, base):
    pendente = AcaoProposta(
        ferramenta="reenviar_produto",
        papel=Papel.ATENDENTE,
        executado_por="agente",
        conversation_id="AT116160",
        order_id="GBH473217",
        valor_rs=260.0,
        motivo="extravio",
    )
    pedido = ferramentas.executar(
        AcaoProposta(
            ferramenta="solicitar_aprovacao",
            papel=Papel.ATENDENTE,
            executado_por="agente",
            conversation_id="AT116160",
            order_id="GBH473217",
            valor_rs=260.0,
            motivo="acima de R$ 200",
        ),
        acao_pendente=pendente,
    )
    aprovacao_id = pedido.referencia_sistema
    assert aprovacao_id == "APR-000001"
    assert ferramentas.aprovacao(aprovacao_id)["acao"] == pendente
    assert ferramentas.aprovacao(aprovacao_id)["estado"] == "pendente"

    ferramentas.executar(
        AcaoProposta(
            ferramenta="aprovar_acao",
            papel=Papel.SUPERVISOR,
            executado_por="supervisor_02",
            aprovacao_id=aprovacao_id,
            motivo="ok",
        )
    )
    assert ferramentas.aprovacao(aprovacao_id)["estado"] == "aprovada"
    assert ferramentas.aprovacao(aprovacao_id)["decidido_por"] == "supervisor_02"

    registro = ferramentas.executar(
        AcaoProposta(**{**pendente.__dict__, "aprovacao_id": aprovacao_id})
    )
    assert registro.aprovado_por == "supervisor_02"


def test_HP_08_rejeicao_e_aprovacao_inexistente(ferramentas):
    with pytest.raises(ValueError):
        ferramentas.executar(
            AcaoProposta(
                ferramenta="rejeitar_acao",
                papel=Papel.SUPERVISOR,
                executado_por="supervisor_02",
                aprovacao_id="APR-999999",
            )
        )


# ---------- HG-12: idempotência ----------


def test_HG_12_reembolso_repetido_nao_duplica(ferramentas, base):
    acao = AcaoProposta(
        ferramenta="reembolsar",
        papel=Papel.ATENDENTE,
        executado_por="agente",
        conversation_id="AT116160",
        order_id="GBH473217",
        valor_rs=80.0,
        motivo="atraso",
    )

    primeiro = ferramentas.executar(acao)
    segundo = ferramentas.executar(acao)

    assert segundo == primeiro
    assert _contar(base, "acoes_agente") == 1
    assert _contar(base, "estornos") == 1


def test_HG_12_mesmo_caso_com_valor_diferente_devolve_o_registro_existente(ferramentas, base):
    """REQUISITOS.md @HG-12: chave de idempotência = conversation_id + order_id + ação.

    O valor não entra na chave: uma nova tentativa com outro valor não gera segundo estorno.
    """
    acao = AcaoProposta(
        ferramenta="reenviar_produto",
        papel=Papel.ATENDENTE,
        executado_por="agente",
        conversation_id="AT116160",
        order_id="GBH473217",
        valor_rs=50.0,
    )

    primeiro = ferramentas.executar(acao)
    segundo = ferramentas.executar(AcaoProposta(**{**acao.__dict__, "valor_rs": 60.0}))

    assert segundo == primeiro
    assert _contar(base, "acoes_agente") == 1
    assert _contar(base, "trocas_reenvios", "acao_id = ?", primeiro.acao_id) == 1


def test_HG_12_acao_sem_dinheiro_nao_e_deduplicada(ferramentas, base):
    acao = AcaoProposta(
        ferramenta="responder_cliente",
        papel=Papel.ATENDENTE,
        executado_por="agente",
        conversation_id="AT116160",
        motivo="Olá",
    )

    ferramentas.executar(acao)
    ferramentas.executar(acao)

    assert _contar(base, "mensagens_enviadas") == 2


# ---------- HG-12 + EC-20: dois itens diferentes na mesma conversa ----------


def _reenvio_item(motivo: str) -> AcaoProposta:
    return AcaoProposta(
        ferramenta="reenviar_produto",
        papel=Papel.ATENDENTE,
        executado_por="agente",
        conversation_id="AT116160",
        order_id="GBH473217",
        valor_rs=50.0,
        motivo=motivo,
    )


def test_HG_12_dois_itens_diferentes_geram_dois_reenvios(ferramentas, base):
    """A chave inclui o item reclamado quando o motivo traz `sku=<SKU>`."""
    primeiro = ferramentas.executar(_reenvio_item("avaria_vazamento: Copo sku=GOC-5043"))
    segundo = ferramentas.executar(_reenvio_item("item_faltante: Card sku=GOC-5059"))

    assert segundo.acao_id != primeiro.acao_id
    assert _contar(base, "acoes_agente", "acao = 'reenviar_produto'") == 2
    skus = {
        linha[0]
        for linha in base.conexao.execute(
            "SELECT sku_enviado FROM trocas_reenvios WHERE acao_id IN (?, ?)",
            (primeiro.acao_id, segundo.acao_id),
        )
    }
    assert skus == {"GOC-5043", "GOC-5059"}


def test_HG_12_mesmo_item_repetido_devolve_o_registro_existente(ferramentas, base):
    primeiro = ferramentas.executar(_reenvio_item("avaria_vazamento: Copo sku=GOC-5043"))
    repetido = ferramentas.executar(_reenvio_item("nova tentativa (timeout) sku=GOC-5043"))

    assert repetido == primeiro
    assert _contar(base, "acoes_agente", "acao = 'reenviar_produto'") == 1


def test_HG_12_sem_item_cai_na_chave_da_conversa(ferramentas, base):
    primeiro = ferramentas.executar(_reenvio_item("avaria_vazamento: Copo sku=GOC-5043"))
    sem_item = ferramentas.executar(_reenvio_item("pedido inteiro"))

    assert sem_item == primeiro
