"""Carga dos CSVs de `docs/` num SQLite ou no Postgres do Neon (EC-21, ADR-002).

Uma tabela por CSV, todas as colunas como TEXT (a conversão de tipos fica no
repositório). `docs/` é aberto só para leitura. Também cria as tabelas, vazias,
onde o agente grava o próprio estado.

Uso: python -m atendimento.dados.carga [--origem docs] [--destino var/atendimento.db | "$DATABASE_URL"]
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

from atendimento.dados.banco import Banco, conectar, e_postgres

SEPARADORES_ACEITOS = ",;\t|"

TABELAS_DO_AGENTE: dict[str, tuple[str, ...]] = {
    # mesmas colunas de contratos.RegistroAcao
    "acoes_agente": (
        "acao_id",
        "conversation_id",
        "order_id",
        "data_hora",
        "sistema",
        "acao",
        "valor_rs",
        "executado_por",
        "aprovado_por",
        "referencia_sistema",
    ),
    "aprovacoes": (
        "aprovacao_id",
        "acao",  # AcaoProposta serializada em JSON
        "solicitado_por",
        "estado",  # pendente, aprovada, rejeitada
        "decidido_por",
        "comentario",
        "solicitado_em",
        "decidido_em",
    ),
    "suspeitas": (
        "suspeita_id",
        "conversation_id",
        "order_id",
        "sinalizado_por",
        "motivo",
        "estado",
        "data_hora",
    ),
    "mensagens_enviadas": (
        "mensagem_id",
        "conversation_id",
        "destino",  # cliente ou time
        "ferramenta",
        "texto",
        "enviado_por",
        "data_hora",
    ),
    "classificacoes": (
        "conversation_id",
        "categoria",
        "classificado_por",
        "data_hora",
    ),
    # HG-02: tentativa de usar ferramenta fora do papel
    "tentativas_bloqueadas": (
        "ferramenta",
        "papel",
        "executado_por",
        "conversation_id",
        "order_id",
        "motivo",
        "data_hora",
    ),
}


def detectar_separador(caminho: Path) -> str:
    """Separador detectado na linha de cabeçalho do CSV (UTF-8)."""
    with open(caminho, encoding="utf-8", newline="") as f:
        cabecalho = f.readline()
    return csv.Sniffer().sniff(cabecalho, delimiters=SEPARADORES_ACEITOS).delimiter


def _ident(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def _criar_tabela(banco: Banco, tabela: str, colunas: list[str] | tuple[str, ...]) -> None:
    definicao = ", ".join(f"{_ident(c)} TEXT" for c in colunas)
    banco.executar(f"DROP TABLE IF EXISTS {_ident(tabela)}")
    banco.executar(f"CREATE TABLE {_ident(tabela)} ({definicao})")


def _ler_csv(caminho: Path) -> tuple[list[str], list[list[str]]]:
    separador = detectar_separador(caminho)
    with open(caminho, encoding="utf-8", newline="") as f:
        leitor = csv.reader(f, delimiter=separador)
        colunas = next(leitor)
        return colunas, list(leitor)


def carregar(origem: Path, destino: Path | str | Banco) -> dict[str, int]:
    """Recria as tabelas de `destino` a partir dos CSVs de `origem`. Devolve linhas por tabela.

    `destino`: caminho SQLite (o arquivo é recriado), URL `postgres://` ou um `Banco`. No
    Postgres cada tabela é apagada e recriada numa transação e carregada por COPY, então rodar
    de novo dá o mesmo resultado (idempotente). As tabelas do estado do agente voltam vazias.
    """
    origem = Path(origem)
    if isinstance(destino, Banco):
        banco, fechar = destino, False
    elif e_postgres(destino):
        banco, fechar = conectar(str(destino)), True
    else:
        caminho = Path(destino)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.unlink(missing_ok=True)
        banco, fechar = conectar(caminho), True
    contagens: dict[str, int] = {}
    try:
        for caminho_csv in sorted(origem.glob("*.csv")):
            colunas, linhas = _ler_csv(caminho_csv)
            with banco.transacao():
                _criar_tabela(banco, caminho_csv.stem, colunas)
                contagens[caminho_csv.stem] = banco.copiar(caminho_csv.stem, colunas, linhas)
        with banco.transacao():
            for tabela, colunas in TABELAS_DO_AGENTE.items():
                _criar_tabela(banco, tabela, colunas)
    finally:
        if fechar:
            banco.fechar()
    return contagens


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Carrega os CSVs de docs/ num SQLite (caminho) ou no Postgres (URL)."
    )
    parser.add_argument("--origem", type=Path, default=Path("docs"))
    parser.add_argument(
        "--destino", default="var/atendimento.db", help='caminho SQLite ou "$DATABASE_URL"'
    )
    parser.add_argument("--esquema", default=None, help="esquema do Postgres (testes)")
    args = parser.parse_args(argv)
    postgres = e_postgres(args.destino)
    destino = conectar(args.destino, esquema=args.esquema) if postgres else args.destino
    inicio = time.perf_counter()
    try:
        contagens = carregar(args.origem, destino)
    finally:
        if postgres:
            destino.fechar()
    segundos = time.perf_counter() - inicio
    for tabela, n in contagens.items():
        print(f"{tabela}: {n} linhas")
    # nunca imprime a URL do Postgres (tem senha)
    onde = "Postgres (DATABASE_URL)" if postgres else args.destino
    print(f"Base gerada em {onde}: {sum(contagens.values())} linhas em {segundos:.1f} s")


if __name__ == "__main__":
    main()
