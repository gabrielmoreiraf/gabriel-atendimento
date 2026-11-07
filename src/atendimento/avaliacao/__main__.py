"""`python -m atendimento.avaliacao`: gera `ingestao/avaliacao_offline.md` a partir de `docs/`.

Com `--leitor claude --amostra 300`, compara o leitor por regras com o leitor com Claude na
mesma amostra e grava `ingestao/avaliacao_leitor_claude.md` (HG-18). Chama a API: rode só
em amostra.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from atendimento.avaliacao import carregar_historico, gerar_relatorio
from atendimento.avaliacao.leitor_claude import INJECTION

RAIZ = Path(__file__).resolve().parents[3]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs", type=Path, default=RAIZ / "docs")
    parser.add_argument("--saida", type=Path, default=None)
    parser.add_argument("--leitor", choices=("regras", "claude"), default="regras")
    parser.add_argument("--amostra", type=int, default=300)
    parser.add_argument("--semente", type=int, default=42)
    args = parser.parse_args(argv)
    if args.leitor == "claude":
        saida = args.saida or RAIZ / "ingestao" / "avaliacao_leitor_claude.md"
        saida.write_text(_comparar_com_claude(args), encoding="utf-8")
    else:
        saida = args.saida or RAIZ / "ingestao" / "avaliacao_offline.md"
        saida.write_text(gerar_relatorio(carregar_historico(args.docs)), encoding="utf-8")
    print(f"Relatório gravado em {saida}")


def _comparar_com_claude(args) -> str:
    from datetime import date

    from dotenv import load_dotenv

    from atendimento.agente.leitor_claude import MODELO, LeitorClaude
    from atendimento.avaliacao.historico import ler_csv
    from atendimento.avaliacao.leitor_claude import (
        amostra_estratificada,
        comparar_leitores,
        relatorio_leitores,
    )

    load_dotenv()  # a chave fica no ambiente do SDK; nunca é lida aqui
    historico = carregar_historico(args.docs)
    textos = {
        cid: "\n".join(t for t in ts if t and t.strip())
        for cid, ts in historico.mensagens_do_cliente.items()
    }
    conversas = {cid: c["tag_agente"] for cid, c in historico.conversas.items() if textos.get(cid)}
    cosmeto = {
        a["conversation_id"] for a in historico.acoes if a["acao"] == "registrar_cosmetovigilancia"
    }
    amostra = amostra_estratificada(
        conversas, args.amostra, semente=args.semente, obrigatorias=cosmeto | INJECTION
    )
    leitor = LeitorClaude(cache=RAIZ / "var" / "cache_leitor_claude")
    resultado = comparar_leitores(
        amostra,
        conversas,
        textos,
        historico.politicas,
        leitor_claude=leitor,
        cosmetovigilancia=cosmeto,
        cupons=[c["codigo"] for c in ler_csv(args.docs / "cupons.csv")],
    )
    return relatorio_leitores(
        resultado, modelo=MODELO, data=date.today().isoformat(), semente=args.semente
    )


if __name__ == "__main__":
    main()
