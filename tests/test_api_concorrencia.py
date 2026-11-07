"""E2E achou IndexError em Base.fila() com rotas em threads diferentes (conexão compartilhada)."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor

from atendimento.dados.repositorio import Base


def test_base_aguenta_leitura_concorrente(tmp_path):
    db = tmp_path / "mini.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE fila_aberta (conversation_id TEXT, data_abertura TEXT, canal TEXT)")
    con.executemany(
        "INSERT INTO fila_aberta VALUES (?, ?, 'email')",
        [(f"AT{i:06d}", f"2026-11-01 {i % 24:02d}:00:00") for i in range(300)],
    )
    con.commit()
    con.close()
    base = Base(db)

    def ler(_):
        fila = base.fila()
        return len(fila), fila[0]["conversation_id"]

    with ThreadPoolExecutor(max_workers=16) as pool:
        resultados = list(pool.map(ler, range(400)))
    assert set(resultados) == {(300, resultados[0][1])}
