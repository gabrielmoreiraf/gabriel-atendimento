"""Verificador de evidência (W3): EC-15..EC-19, Q15 e HG-07.

Casos reais vêm de `tests/fixtures/verificacao/casos_reais.json` (recorte de `docs/`).
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import pytest

from atendimento.contratos import FUSO, Anexo, Item, Pedido, TipoSinal
from atendimento.verificacao import LIMIAR_REENVIOS, SINAIS_DE_CONTEXTO, SINAIS_FORTES, verificar

CASOS = json.loads(
    (Path(__file__).parent / "fixtures" / "verificacao" / "casos_reais.json").read_text(
        encoding="utf-8"
    )
)
PALAVRAS_PROIBIDAS = ("fraude", "golpe", "mentira", "falso", "falsa")


def _pedido(order_id: str) -> Pedido:
    d = CASOS["pedidos"][order_id]
    itens = tuple(Item(**i) for i in d["itens"])
    return Pedido(
        order_id=d["order_id"],
        customer_id=d["customer_id"],
        marca=d["marca"],
        valor=d["valor"],
        status_entrega=d["status_entrega"],
        data_separacao=date.fromisoformat(d["data_separacao"]),
        data_entrega=date.fromisoformat(d["data_entrega"]),
        lote_produto=d["lote_produto"],
        itens=itens,
    )


def _anexo(anexo_id: str) -> Anexo:
    d = dict(CASOS["anexos"][anexo_id])
    if d["exif_data_captura"]:
        d["exif_data_captura"] = datetime.fromisoformat(d["exif_data_captura"]).replace(tzinfo=FUSO)
    return Anexo(**d)


def _tipos(veredicto) -> set[TipoSinal]:
    return {s.tipo for s in veredicto.sinais}


def _sem_exif(anexo: Anexo) -> Anexo:
    return replace(anexo, exif_data_captura=None, exif_software=None)


# ---------- EC-15: sem EXIF é só informativo ----------


def test_EC_15_sem_exif_gera_apenas_sinal_informativo():
    pedido = _pedido("GCH528786")
    anexo = _anexo("IMG000059")  # WhatsApp, sem EXIF, descrição bate com o SKU

    v = verificar(
        pedido=pedido,
        anexos=[anexo],
        anexos_mesmo_hash={anexo.hash_perceptual: [anexo]},
        reenvios_anteriores_cliente=0,
    )

    assert _tipos(v) == {TipoSinal.SEM_EXIF}
    assert v.suspeita is False
    assert "IMG000059" in v.justificativa


def test_EC_15_sem_exif_nao_vira_suspeita_mesmo_em_pedido_caro():
    pedido = replace(_pedido("GCH528786"), valor=5000.0)
    anexo = _anexo("IMG000059")

    v = verificar(
        pedido=pedido,
        anexos=[anexo],
        anexos_mesmo_hash={anexo.hash_perceptual: [anexo]},
        reenvios_anteriores_cliente=0,
    )

    assert v.suspeita is False


# ---------- EC-16: mesmo hash em outro pedido ----------


def test_EC_16_hash_repetido_em_outro_pedido_gera_sinal_e_suspeita():
    pedido = _pedido("GCH525527")
    anexo = _sem_exif(_anexo("IMG000010"))  # isola o sinal de hash
    outro = _anexo("IMG000098")  # mesmo hash, pedido GCH533082

    v = verificar(
        pedido=pedido,
        anexos=[anexo],
        anexos_mesmo_hash={anexo.hash_perceptual: [anexo, outro]},
        reenvios_anteriores_cliente=0,
    )

    sinais = [s for s in v.sinais if s.tipo == TipoSinal.HASH_REPETIDO]
    assert len(sinais) == 1
    assert sinais[0].anexo_id == "IMG000010"
    assert "GCH533082" in sinais[0].descricao
    assert "GCH525527" in sinais[0].descricao
    assert "5e1440cfcdbcaf3f" in sinais[0].descricao
    assert v.suspeita is True


def test_EC_16_mesmo_hash_no_mesmo_pedido_nao_gera_sinal():
    pedido = _pedido("GCH525527")
    anexo = _sem_exif(_anexo("IMG000010"))
    reenviado = replace(anexo, anexo_id="IMG999999", conversation_id="AT999999")

    v = verificar(
        pedido=pedido,
        anexos=[anexo],
        anexos_mesmo_hash={anexo.hash_perceptual: [anexo, reenviado]},
        reenvios_anteriores_cliente=0,
    )

    assert TipoSinal.HASH_REPETIDO not in _tipos(v)
    assert v.suspeita is False


# ---------- EC-17: foto tirada antes da entrega ----------


def test_EC_17_captura_antes_da_entrega_cita_as_duas_datas():
    pedido = _pedido("GCH529021")  # entregue em 2026-08-17
    anexo = _anexo("IMG000071")  # EXIF 2026-07-25 17:12

    v = verificar(
        pedido=pedido,
        anexos=[anexo],
        anexos_mesmo_hash={anexo.hash_perceptual: [anexo]},
        reenvios_anteriores_cliente=0,
    )

    sinais = [s for s in v.sinais if s.tipo == TipoSinal.CAPTURA_ANTES_DA_ENTREGA]
    assert len(sinais) == 1
    assert "25/07/2026" in sinais[0].descricao
    assert "17/08/2026" in sinais[0].descricao
    assert sinais[0].anexo_id == "IMG000071"
    assert v.suspeita is True


def test_EC_17_captura_no_dia_da_entrega_nao_gera_sinal():
    pedido = _pedido("GCH529021")
    anexo = replace(
        _anexo("IMG000071"), exif_data_captura=datetime(2026, 8, 17, 19, 0, tzinfo=FUSO)
    )

    v = verificar(
        pedido=pedido,
        anexos=[anexo],
        anexos_mesmo_hash={anexo.hash_perceptual: [anexo]},
        reenvios_anteriores_cliente=0,
    )

    assert v.sinais == ()
    assert v.suspeita is False


def test_EC_17_pedido_sem_data_de_entrega_nao_gera_sinal():
    pedido = replace(_pedido("GCH529021"), data_entrega=None)
    anexo = _anexo("IMG000071")

    v = verificar(
        pedido=pedido,
        anexos=[anexo],
        anexos_mesmo_hash={anexo.hash_perceptual: [anexo]},
        reenvios_anteriores_cliente=0,
    )

    assert TipoSinal.CAPTURA_ANTES_DA_ENTREGA not in _tipos(v)


# ---------- Editor de imagem ----------


def test_EC_17_exif_software_preenchido_gera_editor_de_imagem():
    pedido = _pedido("GCH529021")
    anexo = replace(
        _anexo("IMG000071"),
        exif_data_captura=datetime(2026, 8, 18, 10, 0, tzinfo=FUSO),
        exif_software="Editor de Fotos do Galaxy",
    )

    v = verificar(
        pedido=pedido,
        anexos=[anexo],
        anexos_mesmo_hash={anexo.hash_perceptual: [anexo]},
        reenvios_anteriores_cliente=0,
    )

    assert _tipos(v) == {TipoSinal.EDITOR_DE_IMAGEM}
    assert "Editor de Fotos do Galaxy" in v.sinais[0].descricao
    assert v.suspeita is True


# ---------- EC-18: personalização divergente ----------


def _pedido_ana() -> Pedido:
    base = _pedido("GCH528786")
    item = replace(base.itens[0], texto_personalizacao="Ana")
    return replace(base, itens=(item,))


def _anexo_com_descricao(descricao: str) -> Anexo:
    return replace(_anexo("IMG000059"), descricao_visual=descricao)


def test_EC_18_nome_do_pedido_impresso_borrado_nao_gera_sinal():
    anexo = _anexo_com_descricao('Copo com o nome "Ana" impresso borrado.')

    v = verificar(
        pedido=_pedido_ana(),
        anexos=[anexo],
        anexos_mesmo_hash={anexo.hash_perceptual: [anexo]},
        reenvios_anteriores_cliente=0,
    )

    assert TipoSinal.PERSONALIZACAO_DIVERGENTE not in _tipos(v)
    assert v.suspeita is False


def test_EC_18_texto_impresso_que_nao_esta_no_pedido_gera_sinal_de_contexto():
    anexo = _anexo_com_descricao('Copo com o nome "Bia" impresso na lateral.')

    v = verificar(
        pedido=_pedido_ana(),
        anexos=[anexo],
        anexos_mesmo_hash={anexo.hash_perceptual: [anexo]},
        reenvios_anteriores_cliente=0,
    )

    sinais = [s for s in v.sinais if s.tipo == TipoSinal.PERSONALIZACAO_DIVERGENTE]
    assert len(sinais) == 1
    assert "Bia" in sinais[0].descricao
    assert "Ana" in sinais[0].descricao
    # sinal de contexto (Q15): o W4 pede nova foto antes de decidir; sozinho não é suspeita
    assert v.suspeita is False


def test_EC_18_nome_sem_aspas_tambem_e_comparado():
    anexo = _anexo_com_descricao("Copo com o nome Bia impresso na lateral.")

    v = verificar(
        pedido=_pedido_ana(),
        anexos=[anexo],
        anexos_mesmo_hash={anexo.hash_perceptual: [anexo]},
        reenvios_anteriores_cliente=0,
    )

    assert TipoSinal.PERSONALIZACAO_DIVERGENTE in _tipos(v)


def test_EC_18_comparacao_ignora_caixa_e_acento():
    base = _pedido_ana()
    item = replace(base.itens[0], texto_personalizacao="Júlia")
    anexo = _anexo_com_descricao('Garrafa com o nome "JULIA" impresso torto.')

    v = verificar(
        pedido=replace(base, itens=(item,)),
        anexos=[anexo],
        anexos_mesmo_hash={anexo.hash_perceptual: [anexo]},
        reenvios_anteriores_cliente=0,
    )

    assert TipoSinal.PERSONALIZACAO_DIVERGENTE not in _tipos(v)


@pytest.mark.parametrize(
    "descricao",
    [
        # descrições reais da base: falam da impressão, mas não citam o texto impresso
        "Copo Daily 600ml Personalizado Nome com a pintura descascada e um amassado lateral.",
        "Copo Life 1100ml Personalizado Nome com o nome impresso diferente do pedido e a arte deslocada para a esquerda.",
        'Mala Trip 20" Personalizada Iniciais com a impressão borrada e as letras ilegíveis.',
        # aspas de polegadas não são texto citado
        'Mala Trip 20" e Mala Trip 24" Personalizadas Iniciais com a impressão borrada.',
    ],
)
def test_EC_18_descricao_sem_texto_citado_nao_gera_sinal(descricao):
    anexo = _anexo_com_descricao(descricao)

    v = verificar(
        pedido=_pedido("GCH528786"),
        anexos=[anexo],
        anexos_mesmo_hash={anexo.hash_perceptual: [anexo]},
        reenvios_anteriores_cliente=0,
    )

    assert TipoSinal.PERSONALIZACAO_DIVERGENTE not in _tipos(v)


def test_EC_18_pedido_sem_personalizacao_nao_gera_sinal():
    base = _pedido("GCH528786")
    item = replace(base.itens[0], texto_personalizacao=None)
    anexo = _anexo_com_descricao('Capinha com o nome "Bia" impresso.')

    v = verificar(
        pedido=replace(base, itens=(item,)),
        anexos=[anexo],
        anexos_mesmo_hash={anexo.hash_perceptual: [anexo]},
        reenvios_anteriores_cliente=0,
    )

    assert TipoSinal.PERSONALIZACAO_DIVERGENTE not in _tipos(v)


# ---------- EC-19: reenvios anteriores ----------


def test_EC_19_sem_reenvios_nao_gera_sinal():
    anexo = _anexo("IMG000059")

    v = verificar(
        pedido=_pedido("GCH528786"),
        anexos=[anexo],
        anexos_mesmo_hash={anexo.hash_perceptual: [anexo]},
        reenvios_anteriores_cliente=0,
    )

    assert TipoSinal.REENVIOS_ANTERIORES not in _tipos(v)


def test_EC_19_um_reenvio_ja_registra_sinal_de_contexto():
    anexo = _anexo("IMG000059")

    v = verificar(
        pedido=_pedido("GCH528786"),
        anexos=[anexo],
        anexos_mesmo_hash={anexo.hash_perceptual: [anexo]},
        reenvios_anteriores_cliente=1,
    )

    sinais = [s for s in v.sinais if s.tipo == TipoSinal.REENVIOS_ANTERIORES]
    assert len(sinais) == 1
    assert "1 reenvio" in sinais[0].descricao
    assert "acima do comum" not in sinais[0].descricao
    assert v.suspeita is False


def test_EC_19_reenvios_acima_do_limiar_citam_acima_do_comum_mas_nao_bastam_sozinhos():
    anexo = _anexo("IMG000059")

    v = verificar(
        pedido=_pedido("GCH528786"),
        anexos=[anexo],
        anexos_mesmo_hash={anexo.hash_perceptual: [anexo]},
        reenvios_anteriores_cliente=LIMIAR_REENVIOS + 1,
    )

    sinais = [s for s in v.sinais if s.tipo == TipoSinal.REENVIOS_ANTERIORES]
    assert len(sinais) == 1
    assert str(LIMIAR_REENVIOS + 1) in sinais[0].descricao
    assert "acima do comum" in sinais[0].descricao
    assert v.suspeita is False


def test_EC_19_limiar_vem_da_distribuicao_da_base():
    # trocas_reenvios.csv: 2 reenvios por cliente ainda é comum (96 clientes); 3+ são 17
    assert LIMIAR_REENVIOS == 2


# ---------- Q15: regra de custo ----------


def test_Q15_apenas_sinais_fortes_tornam_o_caso_suspeito():
    assert SINAIS_FORTES == {
        TipoSinal.HASH_REPETIDO,
        TipoSinal.CAPTURA_ANTES_DA_ENTREGA,
        TipoSinal.EDITOR_DE_IMAGEM,
    }
    assert {
        TipoSinal.SEM_EXIF,
        TipoSinal.REENVIOS_ANTERIORES,
        TipoSinal.PERSONALIZACAO_DIVERGENTE,
    } <= SINAIS_DE_CONTEXTO


def test_Q15_todos_os_sinais_de_contexto_juntos_nao_tornam_suspeito():
    anexo = _anexo_com_descricao('Copo com o nome "Bia" impresso na lateral.')  # sem EXIF

    v = verificar(
        pedido=replace(_pedido_ana(), valor=5000.0),
        anexos=[anexo],
        anexos_mesmo_hash={anexo.hash_perceptual: [anexo]},
        reenvios_anteriores_cliente=LIMIAR_REENVIOS + 2,
    )

    assert _tipos(v) == {
        TipoSinal.SEM_EXIF,
        TipoSinal.PERSONALIZACAO_DIVERGENTE,
        TipoSinal.REENVIOS_ANTERIORES,
    }
    assert v.suspeita is False


def test_Q15_custos_vem_de_parametros():
    anexo = _anexo("IMG000059")

    v = verificar(
        pedido=_pedido("GCH528786"),  # valor R$ 132,80
        anexos=[anexo],
        anexos_mesmo_hash={anexo.hash_perceptual: [anexo]},
        reenvios_anteriores_cliente=0,
    )

    assert v.custo_aceitar_falso_rs == pytest.approx(132.80 * 0.45)
    assert v.custo_sinalizar_verdadeiro_rs == 6.0


def test_Q15_pedido_barato_com_sinal_nao_vira_suspeita():
    # 0,45 × 12,00 = 5,40 ≤ 6,00: sinalizar custa mais do que aceitar
    pedido = replace(_pedido("GCH529021"), valor=12.0)
    anexo = _anexo("IMG000071")

    v = verificar(
        pedido=pedido,
        anexos=[anexo],
        anexos_mesmo_hash={anexo.hash_perceptual: [anexo]},
        reenvios_anteriores_cliente=0,
    )

    assert TipoSinal.CAPTURA_ANTES_DA_ENTREGA in _tipos(v)
    assert v.suspeita is False
    assert "R$ 5,40" in v.justificativa
    assert "R$ 6,00" in v.justificativa


def test_Q15_sem_anexos_nao_ha_sinal_nem_suspeita():
    v = verificar(
        pedido=_pedido("GCH528786"),
        anexos=[],
        anexos_mesmo_hash={},
        reenvios_anteriores_cliente=0,
    )

    assert v.sinais == ()
    assert v.suspeita is False


# ---------- HG-07: linguagem neutra ----------


def test_HG_07_textos_neutros_e_com_fatos():
    pedido = _pedido("GCH525527")
    anexo = _anexo("IMG000010")  # hash repetido + EXIF antes da entrega
    outro = _anexo("IMG000098")

    v = verificar(
        pedido=pedido,
        anexos=[anexo],
        anexos_mesmo_hash={anexo.hash_perceptual: [anexo, outro]},
        reenvios_anteriores_cliente=LIMIAR_REENVIOS + 2,
    )

    assert v.suspeita is True
    assert {
        TipoSinal.HASH_REPETIDO,
        TipoSinal.CAPTURA_ANTES_DA_ENTREGA,
        TipoSinal.REENVIOS_ANTERIORES,
    } <= _tipos(v)
    textos = [v.justificativa, *(s.descricao for s in v.sinais)]
    for texto in textos:
        for palavra in PALAVRAS_PROIBIDAS:
            assert palavra not in texto.lower(), (palavra, texto)
    assert "IMG000010" in v.justificativa
    assert "01/07/2026" in v.justificativa
    assert "04/08/2026" in v.justificativa
