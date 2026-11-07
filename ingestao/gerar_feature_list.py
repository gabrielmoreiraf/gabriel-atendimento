"""Gera feature_list.json a partir dos cenários BDD de REQUISITOS.md.

Uso: python3 -I ingestao/gerar_feature_list.py

Cada cenário (@HP-xx, @EC-xx, @HG-xx) vira uma feature com "passes": false.
Se feature_list.json já existir, o estado de features já revisadas
(passes, revisado_em, evidencia) é preservado; só o subagente revisor muda "passes".
"""

from __future__ import annotations

import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
REQ = RAIZ / "REQUISITOS.md"
SAIDA = RAIZ / "feature_list.json"

CATEGORIA = {"HP": "fluxo_principal_e2e", "EC": "dados_de_borda", "HG": "harness_e_gating"}
SECAO = {"HP": "2.1", "EC": "2.2", "HG": "2.3"}

RE_TAGS = re.compile(r"^\s*(@[\w-]+\s*)+$")
RE_CEN = re.compile(r"^\s*Scenario(?: Outline)?:\s*(.+)$")


def extrair() -> list[dict]:
    linhas = REQ.read_text(encoding="utf-8").splitlines()
    feats = []
    for i, linha in enumerate(linhas):
        if not RE_TAGS.match(linha):
            continue
        tags = re.findall(r"@([\w-]+)", linha)
        ids = [t for t in tags if re.fullmatch(r"(HP|EC|HG)-\d+", t)]
        if not ids or i + 1 >= len(linhas):
            continue
        m = RE_CEN.match(linhas[i + 1])
        if not m:
            continue
        fid = ids[0]
        pref = fid.split("-")[0]
        feats.append(
            {
                "id": fid,
                "titulo": m.group(1).strip(),
                "categoria": CATEGORIA[pref],
                "tags": [t for t in tags if t != fid],
                "requisito": f"REQUISITOS.md#{SECAO[pref]}",
                "teste": f"test_{fid.replace('-', '_')}",
                "passes": False,
                "revisado_em": None,
                "evidencia": None,
            }
        )
    return feats


def main() -> None:
    novas = extrair()
    antigas = {}
    if SAIDA.exists():
        antigas = {f["id"]: f for f in json.loads(SAIDA.read_text(encoding="utf-8"))["features"]}
    for f in novas:
        a = antigas.get(f["id"])
        if a:
            f.update({k: a[k] for k in ("passes", "revisado_em", "evidencia")})
    doc = {
        "projeto": "atendimento_ao_cliente",
        "fonte": "REQUISITOS.md",
        "regra": "Só o subagente revisor (.claude/agents/revisor.md) muda passes para true.",
        "total": len(novas),
        "features": novas,
    }
    SAIDA.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ids = [f["id"] for f in novas]
    assert len(ids) == len(set(ids)), "IDs de cenário duplicados em REQUISITOS.md"
    por_cat = {}
    for f in novas:
        por_cat[f["categoria"]] = por_cat.get(f["categoria"], 0) + 1
    print(f"{len(novas)} features → {SAIDA.name}: {por_cat}")


if __name__ == "__main__":
    main()
