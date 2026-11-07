"""HG-18: comparação regras × Claude na MESMA amostra estratificada por tag (semente fixa)."""

from collections import Counter

from atendimento.agente.leitor import ler
from atendimento.avaliacao.leitor_claude import (
    amostra_estratificada,
    comparar_leitores,
    relatorio_leitores,
)

POLITICAS = {
    "categorias.avaria_vazamento.tag_equivalente": "Avaria",
    "categorias.onde_esta_pedido.tag_equivalente": "Rastreio",
    "categorias.item_faltante.tag_equivalente": "Produto faltando",
}


def _conversas():
    conversas = {}
    for i in range(60):
        conversas[f"AV{i:03d}"] = ("Avaria", "O body mist chegou vazando.")
    for i in range(30):
        conversas[f"RA{i:03d}"] = ("Rastreio", "Cadê o rastreio do meu pedido?")
    for i in range(10):
        conversas[f"RE{i:03d}"] = ("Reclamação produto", "fiquei com o rosto inchado")
    return conversas


def test_HG_18_amostra_e_deterministica_estratificada_e_inclui_as_obrigatorias():
    conversas = {cid: tag for cid, (tag, _) in _conversas().items()}
    obrigatorias = {"RE001", "RE002"}
    a = amostra_estratificada(conversas, 20, semente=42, obrigatorias=obrigatorias)
    b = amostra_estratificada(conversas, 20, semente=42, obrigatorias=obrigatorias)
    assert a == b and len(a) == 20
    assert obrigatorias <= set(a)
    por_tag = Counter(conversas[c] for c in a)
    assert por_tag["Avaria"] > por_tag["Rastreio"] > 0  # proporcional ao tamanho da tag


def test_HG_18_compara_os_dois_leitores_na_mesma_amostra():
    dados = _conversas()
    conversas = {cid: tag for cid, (tag, _) in dados.items()}
    textos = {cid: texto for cid, (_, texto) in dados.items()}

    def claude_que_erra_rastreio(texto, *, cupons=None):
        leitura = ler(texto, cupons=cupons)
        return leitura if leitura.categoria != "rastreio" else ler("O body mist chegou vazando.")

    amostra = amostra_estratificada(conversas, 30, semente=7, obrigatorias={"RE000"})
    r = comparar_leitores(
        amostra,
        conversas,
        textos,
        POLITICAS,
        leitor_claude=claude_que_erra_rastreio,
        cosmetovigilancia={"RE000"},
        injection=set(),
    )
    assert r["por_tag"]["Rastreio"]["regras"] == r["por_tag"]["Rastreio"]["n"]
    assert r["por_tag"]["Rastreio"]["claude"] == 0
    assert r["cosmetovigilancia"] == {"total": 1, "regras": 1, "claude": 1}
    texto = relatorio_leitores(r, modelo="claude-opus-5-5", data="2026-11-07", semente=7)
    assert "claude-opus-5-5" in texto and "30 conversas" in texto and "Rastreio" in texto
