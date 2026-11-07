"""`python -m atendimento.avaliacao`: gera `ingestao/avaliacao_offline.md` a partir de `docs/`."""

from __future__ import annotations

import argparse
from pathlib import Path

from atendimento.avaliacao import carregar_historico, gerar_relatorio

RAIZ = Path(__file__).resolve().parents[3]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs", type=Path, default=RAIZ / "docs")
    parser.add_argument("--saida", type=Path, default=RAIZ / "ingestao" / "avaliacao_offline.md")
    args = parser.parse_args(argv)
    args.saida.write_text(gerar_relatorio(carregar_historico(args.docs)), encoding="utf-8")
    print(f"Relatório gravado em {args.saida}")


if __name__ == "__main__":
    main()
