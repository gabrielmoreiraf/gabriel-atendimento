"""Leitura da base SQLite por ID, devolvendo os contratos de `contratos.py`.

Joins sempre pelos IDs do dicionário de dados. Datas com fuso `contratos.FUSO`.
Dados pessoais do cliente (CPF, e-mail, telefone) saem mascarados.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import date, datetime
from pathlib import Path

from atendimento.contratos import FUSO, AcaoAnterior, Anexo, Item, Pedido
from atendimento.privacidade import mascarar_cpf, mascarar_email, mascarar_telefone

# Ações que movimentam dinheiro (custo para a empresa ou estorno ao cliente).
FERRAMENTAS_COM_DINHEIRO = (
    "reenviar_produto",
    "reimprimir_personalizacao",
    "trocar_produto",
    "reembolsar",
    "cancelar_pedido",
)


def _texto(valor: str | None) -> str | None:
    return valor if valor not in (None, "") else None


def _data(valor: str | None) -> date | None:
    return date.fromisoformat(valor[:10]) if _texto(valor) else None


def _data_hora(valor: str | None) -> datetime | None:
    if not _texto(valor):
        return None
    return datetime.fromisoformat(valor).replace(tzinfo=FUSO)


def _float(valor: str | None) -> float:
    return float(valor) if _texto(valor) else 0.0


class Base:
    """Acesso de leitura à base gerada por `atendimento.dados.carga`."""

    def __init__(self, caminho_db: str | Path):
        self.caminho_db = Path(caminho_db)
        self.conexao = sqlite3.connect(self.caminho_db, check_same_thread=False)
        self.conexao.row_factory = sqlite3.Row
        # A API usa a mesma conexão em mais de uma thread: serializa o acesso (E2E: IndexError).
        self.trava = threading.RLock()

    def _linhas(self, sql: str, *parametros) -> list[sqlite3.Row]:
        with self.trava:
            return self.conexao.execute(sql, parametros).fetchall()

    # ---------- pedidos ----------

    def pedido(self, order_id: str) -> Pedido | None:
        linhas = self._linhas("SELECT * FROM pedidos WHERE order_id = ?", order_id)
        if not linhas:
            return None
        p = linhas[0]
        itens = tuple(
            Item(
                item_id=i["item_id"],
                sku=i["sku"],
                descricao=i["descricao"],
                tipo_item=i["tipo_item"],
                valor_total=_float(i["valor_total"]),
                texto_personalizacao=_texto(i["texto_personalizacao"]),
            )
            for i in self._linhas(
                "SELECT * FROM itens_pedido WHERE order_id = ? ORDER BY CAST(linha AS INTEGER)",
                order_id,
            )
        )
        return Pedido(
            order_id=p["order_id"],
            customer_id=p["customer_id"],
            marca=p["marca"],
            valor=_float(p["valor"]),
            status_entrega=p["status_entrega"],
            data_separacao=_data(p["data_separacao"]),
            data_entrega=_data(p["data_entrega"]),
            lote_produto=_texto(p["lote_produto"]),
            itens=itens,
        )

    def pedido_bruto(self, order_id: str) -> dict | None:
        """Linha completa de `pedidos.csv` (transportadora, rastreio, previsão)."""
        linhas = self._linhas("SELECT * FROM pedidos WHERE order_id = ?", order_id)
        return dict(linhas[0]) if linhas else None

    # ---------- anexos ----------

    @staticmethod
    def _anexo(linha: sqlite3.Row) -> Anexo:
        return Anexo(
            anexo_id=linha["anexo_id"],
            conversation_id=linha["conversation_id"],
            order_id=_texto(linha["order_id"]),
            hash_perceptual=_texto(linha["hash_perceptual"]),
            exif_data_captura=_data_hora(linha["exif_data_captura"]),
            exif_software=_texto(linha["exif_software"]),
            descricao_visual=linha["descricao_visual"],
        )

    def anexos_da_conversa(self, conversation_id: str) -> list[Anexo]:
        linhas = self._linhas(
            "SELECT * FROM anexos_conversas WHERE conversation_id = ? ORDER BY enviado_em",
            conversation_id,
        )
        return [self._anexo(linha) for linha in linhas]

    def anexos_por_hash(self, hash_perceptual: str) -> list[Anexo]:
        linhas = self._linhas(
            "SELECT * FROM anexos_conversas WHERE hash_perceptual = ? ORDER BY enviado_em",
            hash_perceptual,
        )
        return [self._anexo(linha) for linha in linhas]

    # ---------- histórico de ações ----------

    def acoes_com_dinheiro(self, order_id: str) -> list[AcaoAnterior]:
        """Ações com valor no pedido: histórico dos sistemas + ações do agente."""
        marcadores = ", ".join("?" for _ in FERRAMENTAS_COM_DINHEIRO)
        acoes = []
        for tabela in ("acoes_executadas_sistemas", "acoes_agente"):
            linhas = self._linhas(
                f"SELECT * FROM {tabela} WHERE order_id = ? AND acao IN ({marcadores}) "
                "AND valor_rs IS NOT NULL AND valor_rs != '' ORDER BY data_hora, acao_id",
                order_id,
                *FERRAMENTAS_COM_DINHEIRO,
            )
            acoes += [
                AcaoAnterior(
                    acao_id=linha["acao_id"],
                    order_id=linha["order_id"],
                    acao=linha["acao"],
                    valor_rs=_float(linha["valor_rs"]),
                    executado_por=linha["executado_por"],
                    aprovado_por=_texto(linha["aprovado_por"]),
                )
                for linha in linhas
            ]
        return acoes

    def reenvios_do_cliente(self, customer_id: str) -> int:
        """Reenvios do cliente no histórico do OMS (EC-19, SPEC Q15).

        Só `trocas_reenvios.tipo == "reenvio"` (trocas e novas produções não contam) e só o
        histórico: as linhas que o próprio agente grava no OMS simulado (`acao_id` presente
        em `acoes_agente`) ficam de fora.
        """
        return self._linhas(
            "SELECT COUNT(*) FROM trocas_reenvios WHERE customer_id = ? AND tipo = 'reenvio' "
            "AND acao_id NOT IN (SELECT acao_id FROM acoes_agente WHERE acao_id IS NOT NULL)",
            customer_id,
        )[0][0]

    # ---------- conversas ----------

    def fila(self) -> list[dict]:
        linhas = self._linhas("SELECT * FROM fila_aberta ORDER BY data_abertura, conversation_id")
        return [dict(linha) for linha in linhas]

    def mensagens(self, conversation_id: str) -> list[dict]:
        linhas = self._linhas(
            "SELECT * FROM historico_mensagens WHERE conversation_id = ? "
            "ORDER BY timestamp, message_id",
            conversation_id,
        )
        return [dict(linha) for linha in linhas]

    # ---------- cadastros ----------

    def cliente(self, customer_id: str) -> dict | None:
        linhas = self._linhas("SELECT * FROM clientes WHERE customer_id = ?", customer_id)
        if not linhas:
            return None
        cliente = dict(linhas[0])
        for campo, mascarar in (
            ("cpf", mascarar_cpf),
            ("telefone", mascarar_telefone),
            ("email", mascarar_email),
        ):
            if cliente.get(campo):
                cliente[campo] = mascarar(cliente[campo])
        return cliente

    def equipe(self) -> list[dict]:
        return [dict(linha) for linha in self._linhas("SELECT * FROM equipe_atendimento")]

    def politicas(self) -> dict[str, str]:
        return {
            f"{linha['secao']}.{linha['regra']}": linha["valor"]
            for linha in self._linhas("SELECT secao, regra, valor FROM politicas")
        }

    def ferramentas(self) -> dict[str, dict]:
        """Catálogo de `ferramentas.csv` por nome da ferramenta."""
        return {
            linha["ferramenta"]: dict(linha) for linha in self._linhas("SELECT * FROM ferramentas")
        }
