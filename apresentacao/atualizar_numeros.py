"""Copia os números de ingestao/avaliacao_offline.md para o deck e o README.

Os números ficam entre marcadores invisíveis: <!--av:chave-->valor<!--/av-->.
Uso (na raiz do projeto): python3 -I apresentacao/atualizar_numeros.py
"""

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
AVALIACAO = RAIZ / "ingestao" / "avaliacao_offline.md"
ALVOS = [RAIZ / "apresentacao" / "index.html", RAIZ / "README.md"]


def achar(padrao: str, texto: str) -> re.Match:
    m = re.search(padrao, texto, re.S)
    if not m:
        sys.exit(f"padrão não encontrado em {AVALIACAO.name}: {padrao}")
    return m


OBJETIVOS = ("alcada_acumulada", "prazo", "antes_do_recebimento", "troca_repetida")


def _float(valor: str) -> float:
    return float(valor.replace(".", "").replace(",", "."))


def reais_arredondado(valor: str) -> str:
    """'23.522,81' -> '23.523'"""
    numero = round(_float(valor))
    return f"{numero:,}".replace(",", ".")


def extrair(texto: str) -> dict[str, str]:
    v: dict[str, str] = {}
    v["acoes_total"] = achar(r"\*\*(\d+)\*\* ações com dinheiro", texto)[1]
    # Divergências por regra objetiva. `acao_nao_permitida` fica de fora: vem da tag
    # humana da conversa e o relatório a trata como teto, não como previsão.
    motivos = re.findall(r"^\| `(\w+)` \| [^|]+\| (\d+) \| R\$ ([\d.,]+) \|$", texto, re.M)
    objetivos = [(nome, int(n), _float(r)) for nome, n, r in motivos if nome in OBJETIVOS]
    v["motivos"] = ", ".join(f"<code>{nome}</code> {n}" for nome, n, _ in objetivos)
    n_obj = sum(n for _, n, _ in objetivos)
    valor_obj = sum(r for _, _, r in objetivos)
    v["obj_n"] = str(n_obj)
    v["obj_pct"] = f"{100 * n_obj / int(v['acoes_total']):.1f}".replace(".", ",")
    v["obj_valor"] = f"{valor_obj:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    v["obj_valor_arred"] = reais_arredondado(v["obj_valor"])
    m = achar(r"\*\*(\d+) de (\d+)\*\* antes de o dinheiro sair", texto)
    v["m11_barrados"], v["m11_total"] = m[1], m[2]
    linha = achar(r"Primeira ação barrada em cada caso:([^\n]*)", texto)[1]
    for decisao in ("pedir_aprovacao", "escalar", "negar"):
        n = re.search(rf"`{decisao}` em (\d+)", linha)
        v[f"m11_{decisao}"] = n[1] if n else "0"
    v["susp_anexo"] = achar(r"\*\*(\d+)\*\* conversas com anexo", texto)[1]
    v["susp_marcadas"] = achar(r"\*\*(\d+)\*\* como suspeitas", texto)[1]
    v["susp_dinheiro"] = achar(r"Dessas, \*\*(\d+)\*\* receberam", texto)[1]
    m = achar(r"Custo evitado estimado: R\$ ([\d.,]+)", texto)
    v["susp_custo"], v["susp_custo_arred"] = m[1], reais_arredondado(m[1])
    m = achar(
        r"Nas \*\*(\d+)\*\* restantes, a categoria do leitor bate com a\s*`tag_agente` em \*\*(\d+)\*\* \(([\d,]+)%\)",
        texto,
    )
    v["cat_lidas"], v["cat_acertos"], v["cat_pct"] = m[1], m[2], m[3]
    return v


def main() -> None:
    valores = extrair(AVALIACAO.read_text(encoding="utf-8"))
    for alvo in ALVOS:
        if not alvo.exists():
            continue
        texto = alvo.read_text(encoding="utf-8")
        usadas = set(re.findall(r"<!--av:(\w+)-->", texto))
        faltando = usadas - valores.keys()
        if faltando:
            sys.exit(f"{alvo.name}: chaves sem valor: {sorted(faltando)}")
        novo = re.sub(
            r"<!--av:(\w+)-->.*?<!--/av-->",
            lambda m: f"<!--av:{m[1]}-->{valores[m[1]]}<!--/av-->",
            texto,
            flags=re.S,
        )
        alvo.write_text(novo, encoding="utf-8")
        print(f"{alvo.relative_to(RAIZ)}: {len(usadas)} chaves atualizadas")
    for chave, valor in valores.items():
        print(f"  {chave} = {valor}")


if __name__ == "__main__":
    main()
