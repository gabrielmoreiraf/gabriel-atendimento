"""EC-21: leitura robusta dos CSVs e carga no SQLite."""

import csv
import hashlib
import sqlite3
from pathlib import Path

import pytest

from atendimento.dados.carga import TABELAS_DO_AGENTE, carregar, detectar_separador

FIXTURES = Path(__file__).parent / "fixtures" / "dados"
DOCS = Path(__file__).parent.parent / "docs"


def _linhas_csv(caminho: Path) -> int:
    with open(caminho, encoding="utf-8", newline="") as f:
        return sum(1 for _ in csv.reader(f)) - 1


def test_EC_21_detecta_separador_pelo_cabecalho(tmp_path):
    ponto_e_virgula = tmp_path / "a.csv"
    ponto_e_virgula.write_text("id;nome\n1;x\n", encoding="utf-8")
    virgula = tmp_path / "b.csv"
    virgula.write_text('id,texto\n1,"a; b, c"\n', encoding="utf-8")

    assert detectar_separador(ponto_e_virgula) == ";"
    assert detectar_separador(virgula) == ","


def test_EC_21_virgula_e_quebra_de_linha_entre_aspas_nao_quebram_registro(tmp_path):
    origem = tmp_path / "origem"
    origem.mkdir()
    (origem / "msgs.csv").write_text(
        'id,texto\n1,"oi, tudo bem?\nsegunda linha"\n2,ok\n', encoding="utf-8"
    )
    destino = tmp_path / "base.db"

    contagens = carregar(origem, destino)

    assert contagens["msgs"] == 2
    with sqlite3.connect(destino) as con:
        texto = con.execute("SELECT texto FROM msgs WHERE id = '1'").fetchone()[0]
    assert texto == "oi, tudo bem?\nsegunda linha"


def test_EC_21_uma_tabela_por_csv_com_mesma_contagem(tmp_path):
    destino = tmp_path / "base.db"

    contagens = carregar(FIXTURES, destino)

    for arquivo in FIXTURES.glob("*.csv"):
        assert contagens[arquivo.stem] == _linhas_csv(arquivo), arquivo.name


def test_EC_21_cria_tabelas_vazias_do_estado_do_agente(tmp_path):
    destino = tmp_path / "base.db"

    carregar(FIXTURES, destino)

    with sqlite3.connect(destino) as con:
        for tabela in TABELAS_DO_AGENTE:
            assert con.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0] == 0
        colunas = [linha[1] for linha in con.execute("PRAGMA table_info(acoes_agente)")]
    assert colunas == [
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
    ]


def test_EC_21_recarga_substitui_o_banco(tmp_path):
    destino = tmp_path / "base.db"
    carregar(FIXTURES, destino)
    with sqlite3.connect(destino) as con:
        con.execute("INSERT INTO acoes_agente (acao_id) VALUES ('X')")

    carregar(FIXTURES, destino)

    with sqlite3.connect(destino) as con:
        assert con.execute("SELECT COUNT(*) FROM acoes_agente").fetchone()[0] == 0


@pytest.mark.integracao
def test_EC_21_carga_da_base_real_sem_modificar_docs(tmp_path):
    def impressao(pasta: Path) -> dict[str, str]:
        return {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(pasta.glob("*.csv"))
        }

    antes = impressao(DOCS)

    contagens = carregar(DOCS, tmp_path / "base.db")

    assert impressao(DOCS) == antes
    assert len(contagens) == 24
    for arquivo in DOCS.glob("*.csv"):
        assert contagens[arquivo.stem] == _linhas_csv(arquivo), arquivo.name
