"""Stand-ins de W1 (`atendimento.dados.repositorio.Base` e `atendimento.ferramentas.Ferramentas`),
usados só nos testes do agente. Mesmas assinaturas de `tasks/workers/W1.md`."""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

from atendimento.contratos import (
    AGORA,
    FUSO,
    AcaoAnterior,
    AcaoProposta,
    Anexo,
    Item,
    Pedido,
    RegistroAcao,
)

PASTA = Path(__file__).parent
COM_DINHEIRO = {"reenviar_produto", "reimprimir_personalizacao", "trocar_produto", "reembolsar"}
SISTEMA = {
    "reenviar_produto": "ERP",
    "reimprimir_personalizacao": "Producao",
    "trocar_produto": "ERP",
    "reembolsar": "Gateway",
}


def politicas() -> dict[str, str]:
    with open(PASTA / "politicas.csv", encoding="utf-8") as f:
        return {f"{r['secao']}.{r['regra']}": r["valor"] for r in csv.DictReader(f)}


def equipe() -> list[dict]:
    with open(PASTA / "equipe.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def pedido(order_id="GBH000001", valor=120.0, entrega=date(2026, 10, 30), itens=None, **kw):
    itens = itens or (
        Item(f"{order_id}-1", "KSH-1", "Body Mist Baunilha 200ml", "venda", valor, None),
    )
    return Pedido(
        order_id=order_id,
        customer_id=kw.get("customer_id", "CH000001"),
        marca=kw.get("marca", "Kokeshi"),
        valor=valor,
        status_entrega=kw.get("status_entrega", "entregue"),
        data_separacao=kw.get("data_separacao", date(2026, 10, 27)),
        data_entrega=entrega,
        lote_produto=kw.get("lote_produto", "LT1"),
        itens=tuple(itens),
    )


def anexo(conversation_id, order_id, anexo_id="IMG1", hash_="h-unico", captura=None, software=None):
    return Anexo(
        anexo_id=anexo_id,
        conversation_id=conversation_id,
        order_id=order_id,
        hash_perceptual=hash_,
        exif_data_captura=captura,
        exif_software=software,
        descricao_visual="Frasco de body mist com a tampa solta e líquido derramado na caixa.",
    )


class BaseFalsa:
    def __init__(self):
        self._fila: list[dict] = []
        self._mensagens: dict[str, list[dict]] = {}
        self._pedidos: dict[str, Pedido] = {}
        self._anexos: list[Anexo] = []
        self._historico_dinheiro: list[AcaoAnterior] = []
        self.registros: list[RegistroAcao] = []  # preenchido pelas FerramentasFalsas
        self._brutos: dict[str, dict] = {}

    # montagem do cenário
    def conversa(
        self,
        cid,
        textos,
        canal="whatsapp",
        order_id="",
        abertura="2026-11-01 21:00:00",
        atendente_id="",
    ):
        self._fila.append(
            {
                "conversation_id": cid,
                "customer_id": "CH000001",
                "order_id": order_id,
                "marca": "Kokeshi",
                "canal": canal,
                "data_abertura": abertura,
                "status": "aberto",
                "data_primeira_resposta": "",
                "assunto": "",
                "atendente_id": atendente_id,
            }
        )
        self._mensagens[cid] = [
            {"autor": "cliente", "timestamp": abertura, "texto": t} for t in textos
        ]

    def com_pedido(self, p: Pedido):
        self._pedidos[p.order_id] = p

    def com_anexo(self, a: Anexo):
        self._anexos.append(a)

    # interface de W1
    def fila(self):
        return list(self._fila)

    def mensagens(self, cid):
        return list(self._mensagens.get(cid, []))

    def pedido(self, order_id):
        return self._pedidos.get(order_id)

    def pedido_bruto(self, order_id):
        p = self._pedidos.get(order_id)
        if p is None:
            return None
        return {"order_id": order_id, **self._brutos.get(order_id, {})}

    def com_dinheiro_anterior(self, acao: AcaoAnterior):
        self._historico_dinheiro.append(acao)

    def anexos_da_conversa(self, cid):
        return [a for a in self._anexos if a.conversation_id == cid]

    def anexos_por_hash(self, h):
        return [a for a in self._anexos if a.hash_perceptual == h]

    def acoes_com_dinheiro(self, order_id):
        do_agente = [
            AcaoAnterior(r.acao_id, r.order_id, r.acao, r.valor_rs, r.executado_por, r.aprovado_por)
            for r in self.registros
            if r.order_id == order_id and r.acao in COM_DINHEIRO
        ]
        return [a for a in self._historico_dinheiro if a.order_id == order_id] + do_agente

    def reenvios_do_cliente(self, customer_id):
        return 0

    def cliente(self, customer_id):
        return {"customer_id": customer_id}

    def equipe(self):
        return equipe()

    def politicas(self):
        return politicas()


class FerramentasFalsas:
    def __init__(self, base: BaseFalsa):
        self.base = base
        self.agora = AGORA
        self.aprovacoes: dict[str, dict] = {}
        self.areas: list[tuple[str, str | None]] = []
        self.pagamentos: dict[str, list[dict]] = {}
        self.propostas: list[AcaoProposta] = []
        self.rastreios: dict[str, list[dict]] = {}
        self.consultas_rastreio: list[str] = []
        self.fichas: dict[str, str] = {}
        self.cupons: dict[str, dict] = {}
        self.duvidas_respondidas: list[tuple[str, str | None]] = []

    def responder_duvida(self, conversation_id, *, sku=None, executado_por="agente", papel=None):
        if sku not in self.fichas:
            return {"sku": sku, "resposta": None, "precisa_pessoa": True, "motivo": "sem ficha"}
        self.duvidas_respondidas.append((conversation_id, sku))
        return {"sku": sku, "resposta": self.fichas[sku], "precisa_pessoa": False, "motivo": ""}

    def validar_cupom(self, codigo, *, order_id=None, conversation_id=None, **_):
        return {
            "codigo": codigo,
            "order_id": order_id,
            "referencia": "CUP-1",
            **self.cupons[codigo],
        }

    def consultar_rastreio(self, order_id, *, conversation_id=None, executado_por="agente"):
        self.consultas_rastreio.append(order_id)
        return list(self.rastreios.get(order_id, []))

    def verificar_pagamento(self, order_id, *, conversation_id=None, executado_por="agente"):
        return list(self.pagamentos.get(order_id, []))

    def aprovacao(self, aprovacao_id: str) -> dict | None:
        return self.aprovacoes.get(aprovacao_id)

    def executar(
        self, acao: AcaoProposta, *, acao_pendente=None, area=None, decisao=None
    ) -> RegistroAcao:
        if acao.ferramenta == "decidir_suspeita":
            if decisao not in ("procedente", "improcedente"):
                raise ValueError("decidir_suspeita exige decisao")
            sinalizou = {
                p.executado_por
                for p in self.propostas
                if p.ferramenta == "sinalizar_suspeita"
                and p.conversation_id == acao.conversation_id
            }
            if acao.executado_por in sinalizou:
                raise PermissionError("quem sinalizou não decide a suspeita (HG-04)")
        if acao.ferramenta == "solicitar_aprovacao" and acao_pendente is None:
            raise ValueError("solicitar_aprovacao exige acao_pendente")
        self.areas.append((acao.ferramenta, area))
        self.propostas.append(acao)
        if acao.ferramenta in ("aprovar_acao", "rejeitar_acao"):
            aprovacao = self.aprovacoes[acao.aprovacao_id]
            if aprovacao["estado"] != "pendente":
                raise ValueError("aprovação já decidida")
            aprovacao["estado"] = "aprovada" if acao.ferramenta == "aprovar_acao" else "rejeitada"
            aprovacao["decidido_por"] = acao.executado_por
        n = len(self.base.registros) + 1
        registro = RegistroAcao(
            acao_id=f"AG{n:06d}",
            conversation_id=acao.conversation_id,
            order_id=acao.order_id,
            data_hora=self.agora,
            sistema=SISTEMA.get(acao.ferramenta, "Atendimento"),
            acao=acao.ferramenta,
            valor_rs=acao.valor_rs,
            executado_por=acao.executado_por,
            aprovado_por=acao.aprovado_por,
            referencia_sistema=f"{acao.ferramenta[:5].upper()}-{n:06d}",
        )
        self.base.registros.append(registro)
        if acao.ferramenta == "solicitar_aprovacao":
            self.aprovacoes[registro.referencia_sistema] = {
                "aprovacao_id": registro.referencia_sistema,
                "acao": acao_pendente,
                "solicitado_por": acao.executado_por,
                "estado": "pendente",
                "decidido_por": None,
            }
        return registro


def captura(dia: int) -> datetime:
    return datetime(2026, 10, dia, 12, 0, tzinfo=FUSO)


class ReplayFalso:
    """Conversas do histórico (fora da fila de hoje) para o modo replay."""

    def __init__(self, base: BaseFalsa):
        self.base = base
        self._conversas: dict[str, dict] = {}
        self.historico_acoes: list[dict] = []

    def historica(self, cid, textos, order_id, abertura, canal="whatsapp"):
        self._conversas[cid] = {
            "conversation_id": cid,
            "customer_id": "CH000001",
            "order_id": order_id,
            "marca": "Gocase",
            "canal": canal,
            "data_abertura": abertura,
            "assunto": "",
            "tag_agente": "Avaria",
        }
        self.base._mensagens[cid] = [
            {"autor": "cliente", "timestamp": abertura, "texto": t} for t in textos
        ]

    def conversas_com_anexo(self):
        ids = {a.conversation_id for a in self.base._anexos}
        return [c for cid, c in self._conversas.items() if cid in ids]

    def conversa(self, cid):
        return self._conversas.get(cid)

    def acoes_futuras(self, order_id, agora):
        return set()

    def conversas_do_pedido(self, order_id):
        return [c for c in self._conversas.values() if c["order_id"] == order_id]

    def acoes_do_pedido(self, order_id, agora):
        """Ações já registradas no pedido (histórico dos sistemas + agente), antes de `agora`."""
        do_agente = [
            {
                "acao_id": r.acao_id,
                "conversation_id": r.conversation_id,
                "acao": r.acao,
                "data_hora": str(r.data_hora),
                "referencia_sistema": r.referencia_sistema,
            }
            for r in self.base.registros
            if r.order_id == order_id
        ]
        return [a for a in self.historico_acoes if a["order_id"] == order_id] + do_agente
