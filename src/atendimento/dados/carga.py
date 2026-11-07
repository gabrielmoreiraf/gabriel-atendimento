"""Carga dos CSVs de `docs/` num SQLite (EC-21).

Uma tabela por CSV, todas as colunas como TEXT (a conversão de tipos fica no
repositório). `docs/` é aberto só para leitura. Também cria as tabelas, vazias,
onde o agente grava o próprio estado.

Uso: python -m atendimento.dados.carga [--origem docs] [--destino var/atendimento.db]
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path

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


def _criar_tabela(con: sqlite3.Connection, tabela: str, colunas: list[str] | tuple[str, ...]):
    definicao = ", ".join(f"{_ident(c)} TEXT" for c in colunas)
    con.execute(f"CREATE TABLE {_ident(tabela)} ({definicao})")


def _carregar_csv(con: sqlite3.Connection, caminho: Path) -> int:
    separador = detectar_separador(caminho)
    with open(caminho, encoding="utf-8", newline="") as f:
        leitor = csv.reader(f, delimiter=separador)
        colunas = next(leitor)
        _criar_tabela(con, caminho.stem, colunas)
        marcadores = ", ".join("?" for _ in colunas)
        linhas = list(leitor)
    con.executemany(f"INSERT INTO {_ident(caminho.stem)} VALUES ({marcadores})", linhas)
    return len(linhas)


def carregar(origem: Path, destino: Path) -> dict[str, int]:
    """Recria `destino` a partir dos CSVs de `origem`. Devolve linhas por tabela."""
    origem, destino = Path(origem), Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.unlink(missing_ok=True)
    contagens: dict[str, int] = {}
    con = sqlite3.connect(destino)
    try:
        with con:
            for caminho in sorted(origem.glob("*.csv")):
                contagens[caminho.stem] = _carregar_csv(con, caminho)
            for tabela, colunas in TABELAS_DO_AGENTE.items():
                _criar_tabela(con, tabela, colunas)
    finally:
        con.close()
    return contagens


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Carrega os CSVs de docs/ num SQLite.")
    parser.add_argument("--origem", type=Path, default=Path("docs"))
    parser.add_argument("--destino", type=Path, default=Path("var/atendimento.db"))
    args = parser.parse_args(argv)
    contagens = carregar(args.origem, args.destino)
    for tabela, n in contagens.items():
        print(f"{tabela}: {n} linhas")
    print(f"Base gerada em {args.destino}")


if __name__ == "__main__":
    main()
