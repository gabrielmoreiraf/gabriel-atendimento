"""Camada de banco única para SQLite (testes e modo local) e Postgres (Neon, no Vercel).

Contrato 1 de `tasks/vercel/plan.md` (ADR-002):

- `conectar(url)`: `postgres://`/`postgresql://` → Postgres (psycopg 3); outro valor → caminho de
  arquivo SQLite. Sem `url`: `DATABASE_URL` do ambiente, senão `var/atendimento.db`.
- SQL **sempre com `?`**; no Postgres o Banco troca por `%s` (e protege `%` literal).
- `executar` devolve `list[dict]`; `executar_um` devolve `dict | None`.
- Tipos iguais nos dois: `NUMERIC`/`REAL` → `float`; `DATE` → `date`; `TIMESTAMPTZ` →
  `datetime` com fuso; `JSON` → `dict`/`list` (parâmetro `dict`/`list` vira JSON).
- `transacao()` aninhável; `trava(nome)`: `pg_advisory_lock` no Postgres, `threading.RLock`
  por nome no SQLite.
- `tipo_id_auto`: trecho de DDL para id autoincremental (`INTEGER PRIMARY KEY AUTOINCREMENT`
  / `BIGSERIAL PRIMARY KEY`). `tabelas()`: nomes das tabelas existentes.

A URL do Postgres nunca aparece em `repr`, logs ou mensagens de erro deste módulo.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import zlib
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

__all__ = ["Banco", "conectar", "e_postgres"]

CAMINHO_PADRAO = Path("var") / "atendimento.db"


def e_postgres(url: str | os.PathLike | None) -> bool:
    return isinstance(url, str) and url.startswith(("postgres://", "postgresql://"))


def conectar(url: str | os.PathLike | None = None, *, esquema: str | None = None) -> Banco:
    """Abre o banco. `esquema` (só Postgres) aponta o `search_path` para outro esquema."""
    if url is None:
        url = os.environ.get("DATABASE_URL") or CAMINHO_PADRAO
    if e_postgres(url):
        return _BancoPostgres(str(url), esquema=esquema)
    return _BancoSqlite(Path(url))


def _para_python(valor: Any) -> Any:
    return float(valor) if isinstance(valor, Decimal) else valor


class Banco:
    """Interface comum. Use `conectar()`; não instancie direto."""

    dialeto: str = ""
    tipo_id_auto: str = ""

    def __init__(self) -> None:
        # Uma conexão por Banco, compartilhada entre threads: todo acesso passa por esta trava.
        self.trava_conexao = threading.RLock()
        self._profundidade = 0

    # ---------- API pública ----------

    def executar(self, sql: str, params: Sequence[Any] = ()) -> list[dict]:
        with self.trava_conexao:
            linhas = self._executar(sql, tuple(params))
            if self._profundidade == 0:
                self._confirmar()
            return linhas

    def executar_um(self, sql: str, params: Sequence[Any] = ()) -> dict | None:
        linhas = self.executar(sql, params)
        return linhas[0] if linhas else None

    def executar_muitos(self, sql: str, lote: Iterable[Sequence[Any]]) -> None:
        with self.trava_conexao:
            self._executar_muitos(sql, [tuple(p) for p in lote])
            if self._profundidade == 0:
                self._confirmar()

    @contextmanager
    def transacao(self) -> Iterator[Banco]:
        """Tudo dentro vira uma transação só (aninhar é seguro: só a externa confirma)."""
        with self.trava_conexao:
            self._profundidade += 1
            try:
                yield self
            except BaseException:
                self._profundidade -= 1
                if self._profundidade == 0:
                    self._desfazer()
                raise
            self._profundidade -= 1
            if self._profundidade == 0:
                self._confirmar()

    def trava(self, nome: str):
        raise NotImplementedError

    def tabelas(self) -> set[str]:
        raise NotImplementedError

    def fechar(self) -> None:
        self.conexao.close()

    def __repr__(self) -> str:  # nunca mostra a URL
        return f"<Banco {self.dialeto}>"

    # ---------- por dialeto ----------

    conexao: Any

    def _executar(self, sql: str, params: tuple) -> list[dict]:
        raise NotImplementedError

    def _executar_muitos(self, sql: str, lote: list[tuple]) -> None:
        raise NotImplementedError

    def _confirmar(self) -> None:
        self.conexao.commit()

    def _desfazer(self) -> None:
        self.conexao.rollback()


# ---------- SQLite ----------


def _registrar_tipos_sqlite() -> None:
    sqlite3.register_adapter(datetime, lambda v: v.isoformat())
    sqlite3.register_adapter(date, lambda v: v.isoformat())
    sqlite3.register_adapter(dict, lambda v: json.dumps(v, ensure_ascii=False))
    sqlite3.register_adapter(list, lambda v: json.dumps(v, ensure_ascii=False))
    sqlite3.register_adapter(Decimal, float)
    texto = bytes.decode
    for tipo in ("TIMESTAMPTZ", "TIMESTAMP"):
        sqlite3.register_converter(tipo, lambda b: datetime.fromisoformat(texto(b)))
    sqlite3.register_converter("DATE", lambda b: date.fromisoformat(texto(b)[:10]))
    sqlite3.register_converter("JSON", lambda b: json.loads(texto(b)))
    sqlite3.register_converter("JSONB", lambda b: json.loads(texto(b)))
    for tipo in ("NUMERIC", "REAL", "DECIMAL", "DOUBLE"):
        sqlite3.register_converter(tipo, lambda b: float(texto(b)))


_registrar_tipos_sqlite()


class _BancoSqlite(Banco):
    dialeto = "sqlite"
    tipo_id_auto = "INTEGER PRIMARY KEY AUTOINCREMENT"

    def __init__(self, caminho: Path):
        super().__init__()
        self.caminho = caminho
        if str(caminho) != ":memory:":
            caminho.parent.mkdir(parents=True, exist_ok=True)
        self.conexao = sqlite3.connect(
            caminho, check_same_thread=False, detect_types=sqlite3.PARSE_DECLTYPES
        )
        self.conexao.row_factory = sqlite3.Row
        self._travas: dict[str, threading.RLock] = {}
        self._travas_guarda = threading.Lock()

    def _executar(self, sql: str, params: tuple) -> list[dict]:
        cursor = self.conexao.execute(sql, params)
        if cursor.description is None:
            return []
        return [{k: _para_python(linha[k]) for k in linha.keys()} for linha in cursor.fetchall()]

    def _executar_muitos(self, sql: str, lote: list[tuple]) -> None:
        self.conexao.executemany(sql, lote)

    @contextmanager
    def trava(self, nome: str):
        with self._travas_guarda:
            trava = self._travas.setdefault(nome, threading.RLock())
        with trava:
            yield

    def tabelas(self) -> set[str]:
        linhas = self.executar("SELECT name FROM sqlite_master WHERE type = 'table'")
        return {linha["name"] for linha in linhas}


# ---------- Postgres ----------


def _traduzir(sql: str) -> str:
    """`?` → `%s` fora de texto literal; `%` literal → `%%` (psycopg com parâmetros)."""
    saida: list[str] = []
    em_texto = False
    for caractere in sql:
        if caractere == "'":
            em_texto = not em_texto
            saida.append(caractere)
        elif caractere == "%":
            saida.append("%%")
        elif caractere == "?" and not em_texto:
            saida.append("%s")
        else:
            saida.append(caractere)
    return "".join(saida)


class _BancoPostgres(Banco):
    dialeto = "postgres"
    tipo_id_auto = "BIGSERIAL PRIMARY KEY"

    def __init__(self, url: str, *, esquema: str | None = None):
        import psycopg
        from psycopg.rows import dict_row

        super().__init__()
        self._psycopg = psycopg
        self._url = url  # guardado só para abrir a conexão da trava; nunca exposto
        try:
            self.conexao = psycopg.connect(url, row_factory=dict_row, autocommit=True)
        except psycopg.OperationalError as erro:  # sem ecoar a URL
            raise ConnectionError(f"não conectou ao Postgres ({type(erro).__name__})") from None
        self.esquema = esquema
        if esquema:
            self.conexao.execute(f'CREATE SCHEMA IF NOT EXISTS "{esquema}"')
            self.conexao.execute(f'SET search_path TO "{esquema}"')
        self.conexao.execute("SET TIME ZONE 'America/Sao_Paulo'")
        self._transacao_pg = None

    def _parametros(self, params: tuple) -> tuple:
        from psycopg.types.json import Jsonb

        return tuple(Jsonb(p) if isinstance(p, dict | list) else p for p in params)

    def _executar(self, sql: str, params: tuple) -> list[dict]:
        with self.conexao.cursor() as cursor:
            cursor.execute(_traduzir(sql), self._parametros(params))
            if cursor.description is None:
                return []
            return [{k: _para_python(v) for k, v in linha.items()} for linha in cursor.fetchall()]

    def _executar_muitos(self, sql: str, lote: list[tuple]) -> None:
        with self.conexao.cursor() as cursor:
            cursor.executemany(_traduzir(sql), [self._parametros(p) for p in lote])

    @contextmanager
    def transacao(self) -> Iterator[Banco]:
        with self.trava_conexao:
            self._profundidade += 1
            try:
                with self.conexao.transaction():
                    yield self
            finally:
                self._profundidade -= 1

    def _confirmar(self) -> None:  # autocommit fora de `transacao()`
        pass

    def _desfazer(self) -> None:
        pass

    @contextmanager
    def trava(self, nome: str):
        """Advisory lock do Postgres numa conexão própria: vale entre instâncias do Vercel.

        Usa `pg_advisory_xact_lock` dentro de uma transação aberta durante todo o bloco: com o
        pooler do Neon (modo transação), o lock de sessão não segura; o de transação, sim.
        """
        chave = zlib.crc32(nome.encode("utf-8"))
        with self._psycopg.connect(self._url, autocommit=True) as conexao:
            with conexao.transaction():
                conexao.execute("SELECT pg_advisory_xact_lock(%s)", (chave,))
                yield

    def tabelas(self) -> set[str]:
        linhas = self.executar(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()"
        )
        return {linha["table_name"] for linha in linhas}
