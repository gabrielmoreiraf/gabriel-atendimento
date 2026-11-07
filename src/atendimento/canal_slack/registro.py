"""Onde o canal do Slack guarda o que já postou: `ts` e estado de cada mensagem, incidentes
já anunciados e o placar do último resumo.

No Vercel (modo HTTP) cada requisição pode cair numa instância nova, então o registro vai
para o banco (`RegistroBanco`, contrato do W3: `Banco.executar(sql com ?, params)`, SQLite ou
Postgres). Localmente (Socket Mode) a memória do processo basta (`RegistroMemoria`).
"""

from __future__ import annotations

import json
import threading


class RegistroMemoria:
    def __init__(self):
        self._mensagens: dict[str, dict] = {}
        self._incidentes: set[str] = set()
        self._placar: dict | None = None
        self._trava = threading.Lock()

    def mensagem(self, mensagem_id: str) -> dict | None:
        registro = self._mensagens.get(mensagem_id)
        return dict(registro) if registro else None

    def mensagem_por_ts(self, ts: str) -> str | None:
        return next((mid for mid, r in self._mensagens.items() if r["ts"] == ts), None)

    def salvar_mensagem(self, mensagem_id: str, ts: str, estado: str | None) -> None:
        with self._trava:
            self._mensagens[mensagem_id] = {"ts": ts, "estado": estado}

    def incidente_visto(self, incidente_id: str) -> bool:
        return incidente_id in self._incidentes

    def marcar_incidente(self, incidente_id: str) -> bool:
        """True se é a primeira vez (o incidente ainda não foi anunciado)."""
        with self._trava:
            novo = incidente_id not in self._incidentes
            self._incidentes.add(incidente_id)
            return novo

    def ultimo_placar(self) -> dict | None:
        return dict(self._placar) if self._placar is not None else None

    def salvar_placar(self, placar: dict) -> None:
        self._placar = dict(placar)


class RegistroBanco:
    """Mesmo contrato, em duas tabelas portáveis (SQLite e Postgres)."""

    DDL = (
        "CREATE TABLE IF NOT EXISTS slack_mensagens ("
        "mensagem_id TEXT PRIMARY KEY, ts TEXT NOT NULL, estado TEXT)",
        "CREATE TABLE IF NOT EXISTS slack_marcas (chave TEXT PRIMARY KEY, valor TEXT)",
    )

    def __init__(self, banco):
        self.banco = banco
        for ddl in self.DDL:
            self.banco.executar(ddl)

    def mensagem(self, mensagem_id: str) -> dict | None:
        linhas = self.banco.executar(
            "SELECT ts, estado FROM slack_mensagens WHERE mensagem_id = ?", (mensagem_id,)
        )
        return {"ts": linhas[0]["ts"], "estado": linhas[0]["estado"]} if linhas else None

    def mensagem_por_ts(self, ts: str) -> str | None:
        linhas = self.banco.executar("SELECT mensagem_id FROM slack_mensagens WHERE ts = ?", (ts,))
        return linhas[0]["mensagem_id"] if linhas else None

    def salvar_mensagem(self, mensagem_id: str, ts: str, estado: str | None) -> None:
        self.banco.executar(
            "INSERT INTO slack_mensagens (mensagem_id, ts, estado) VALUES (?, ?, ?) "
            "ON CONFLICT (mensagem_id) DO UPDATE SET ts = excluded.ts, estado = excluded.estado",
            (mensagem_id, ts, estado),
        )

    def _marca(self, chave: str) -> str | None:
        linhas = self.banco.executar("SELECT valor FROM slack_marcas WHERE chave = ?", (chave,))
        return linhas[0]["valor"] if linhas else None

    def _marcar(self, chave: str, valor: str) -> None:
        self.banco.executar(
            "INSERT INTO slack_marcas (chave, valor) VALUES (?, ?) "
            "ON CONFLICT (chave) DO UPDATE SET valor = excluded.valor",
            (chave, valor),
        )

    def incidente_visto(self, incidente_id: str) -> bool:
        return self._marca(f"incidente:{incidente_id}") is not None

    def marcar_incidente(self, incidente_id: str) -> bool:
        if self.incidente_visto(incidente_id):
            return False
        self._marcar(f"incidente:{incidente_id}", "1")
        return True

    def ultimo_placar(self) -> dict | None:
        valor = self._marca("ultimo_placar")
        return json.loads(valor) if valor else None

    def salvar_placar(self, placar: dict) -> None:
        self._marcar("ultimo_placar", json.dumps(placar, sort_keys=True))
