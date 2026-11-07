"""HG-18: leitor por regras × leitor com Claude, na MESMA amostra do histórico.

Amostra estratificada pela `tag_agente` humana (semente fixa), proporcional ao tamanho de
cada tag, que sempre inclui as conversas com `registrar_cosmetovigilancia`
(`acoes_executadas_sistemas.csv`) e as de instrução embutida (HG-09). Rodar só em amostra:
cada conversa nova é uma chamada paga à API (o cache em `var/` evita pagar de novo).
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from atendimento.agente.leitor import ler
from atendimento.avaliacao.categoria import tag_da_categoria

INJECTION = {"AT105778", "AT108856", "AT116445"}  # REQUISITOS.md, HG-09


def amostra_estratificada(
    conversas: dict[str, str], n: int, *, semente: int, obrigatorias: set[str] = frozenset()
) -> list[str]:
    """`conversas`: conversation_id -> tag humana. Devolve `n` ids, ordenados."""
    sorteio = random.Random(semente)
    escolhidas = set(obrigatorias) & set(conversas)
    restante = max(n - len(escolhidas), 0)
    por_tag: dict[str, list[str]] = {}
    for cid, tag in sorted(conversas.items()):
        if cid not in escolhidas:
            por_tag.setdefault(tag, []).append(cid)
    total = sum(len(v) for v in por_tag.values())
    if total == 0 or restante == 0:
        return sorted(escolhidas)
    # maiores restos: cotas proporcionais que somam exatamente `restante`
    cotas = {tag: restante * len(v) / total for tag, v in por_tag.items()}
    inteiras = {tag: min(int(c), len(por_tag[tag])) for tag, c in cotas.items()}
    sobra = restante - sum(inteiras.values())
    for tag in sorted(cotas, key=lambda t: (cotas[t] - int(cotas[t]), t), reverse=True):
        if sobra <= 0:
            break
        if inteiras[tag] < len(por_tag[tag]):
            inteiras[tag] += 1
            sobra -= 1
    for tag, quantas in sorted(inteiras.items()):
        escolhidas.update(sorteio.sample(por_tag[tag], quantas))
    return sorted(escolhidas)


def comparar_leitores(
    amostra: list[str],
    conversas: dict[str, str],
    textos: dict[str, str],
    politicas: dict[str, str],
    *,
    leitor_claude: Callable,
    cosmetovigilancia: set[str],
    injection: set[str] = INJECTION,
    cupons: list[str] | None = None,
    paralelo: int = 8,
) -> dict:
    def com_claude(cid: str):
        return leitor_claude(textos[cid], cupons=cupons)

    with ThreadPoolExecutor(max_workers=paralelo) as pool:
        do_claude = dict(zip(amostra, pool.map(com_claude, amostra), strict=True))
    das_regras = {cid: ler(textos[cid], cupons=cupons) for cid in amostra}

    por_tag: dict[str, dict] = {}
    for cid in amostra:
        tag = conversas[cid]
        linha = por_tag.setdefault(tag, {"n": 0, "regras": 0, "claude": 0})
        linha["n"] += 1
        linha["regras"] += tag_da_categoria(das_regras[cid].categoria, politicas) == tag
        linha["claude"] += tag_da_categoria(do_claude[cid].categoria, politicas) == tag

    def sensivel(leitura) -> bool:
        return leitura.sensivel or leitura.categoria == "reacao_adversa"

    cosmeto = set(amostra) & cosmetovigilancia
    injec = set(amostra) & injection
    return {
        "amostra": len(amostra),
        "por_tag": por_tag,
        "regras": sum(t["regras"] for t in por_tag.values()),
        "claude": sum(t["claude"] for t in por_tag.values()),
        "cosmetovigilancia": {
            "total": len(cosmeto),
            "regras": sum(sensivel(das_regras[c]) for c in cosmeto),
            "claude": sum(sensivel(do_claude[c]) for c in cosmeto),
        },
        "injection": {
            "total": len(injec),
            "regras": sum(das_regras[c].instrucao_embutida for c in injec),
            "claude": sum(do_claude[c].instrucao_embutida for c in injec),
        },
        "mudou_categoria": sum(das_regras[c].categoria != do_claude[c].categoria for c in amostra),
        "leitor": leitor_claude,
    }


def _pct(parte: int, total: int) -> str:
    return f"{100 * parte / total:.1f}%" if total else "-"


def relatorio_leitores(r: dict, *, modelo: str, data: str, semente: int) -> str:
    leitor = r["leitor"]
    falhas = Counter(getattr(leitor, "falhas", []))
    chamadas = getattr(leitor, "chamadas", 0)
    custo = getattr(leitor, "custo_usd", 0.0)
    linhas = [
        f"| {tag} | {t['n']} | {t['regras']} ({_pct(t['regras'], t['n'])}) | "
        f"{t['claude']} ({_pct(t['claude'], t['n'])}) |"
        for tag, t in sorted(r["por_tag"].items(), key=lambda kv: -kv[1]["n"])
    ]
    c, i, n = r["cosmetovigilancia"], r["injection"], r["amostra"]
    return f"""# Avaliação do leitor: regras × Claude (HG-18)

- **Modelo:** `{modelo}` (padrão da skill `claude-api`, `effort: low`, saída estruturada)
- **Amostra:** {n} conversas do histórico com mensagem do cliente, estratificada pela
  `tag_agente` (semente {semente}), sempre com as conversas de cosmetovigilância e de
  instrução embutida
- **Data da medição:** {data}
- **Gerado por:** `uv run python -m atendimento.avaliacao --leitor claude --amostra {n}`

## Acerto de categoria contra a tag humana

A categoria de cada leitor vira tag por `politicas.categorias.<categoria>.tag_equivalente`
(mesmo critério de `ingestao/avaliacao_offline.md`, seção 3).

| leitor | acertos | acerto |
| --- | --- | --- |
| regras | {r["regras"]} | {_pct(r["regras"], n)} |
| Claude (com a rede de segurança) | {r["claude"]} | {_pct(r["claude"], n)} |

| tag humana | conversas | regras | Claude |
| --- | --- | --- | --- |
{chr(10).join(linhas)}

O Claude mudou a categoria das regras em {r["mudou_categoria"]} das {n} conversas.

## Segurança

| medida | total na amostra | regras | Claude (com a rede) |
| --- | --- | --- | --- |
| cosmetovigilância vista como sensível (HG-06) | {c["total"]} | {c["regras"]} | {c["claude"]} |
| instrução embutida sinalizada (HG-09) | {i["total"]} | {i["regras"]} | {i["claude"]} |

## Custo e falhas

- Chamadas pagas nesta execução: {chamadas} (as demais vieram do cache em `var/`).
- Custo estimado desta execução: US$ {custo:.2f} (tokens de `usage` × US$ 4/MTok de entrada e
  US$ 20/MTok de saída, tabela da skill `claude-api` para `{modelo}`).
- Quedas para o leitor por regras (HG-13): {sum(falhas.values())}
  ({", ".join(f"{k}: {v}" for k, v in sorted(falhas.items())) or "nenhuma"}).
"""
