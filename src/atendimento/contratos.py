"""Contratos compartilhados entre os módulos do MVP.

Este arquivo é a fronteira entre os workers paralelos (ver `tasks/plan.md`).
Só o maestro altera este arquivo; um worker que precisar de mudança pede ao maestro.
Os módulos de política e de verificação recebem estes objetos prontos e não leem CSV:
quem monta os objetos a partir da base é `atendimento.dados`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")
# "Agora" do projeto. Nunca use o relógio do sistema.
AGORA = datetime(2026, 11, 2, 8, 0, tzinfo=FUSO)


class Papel(StrEnum):
    ATENDENTE = "atendente"
    ANALISTA = "analista"
    SUPERVISOR = "supervisor"


class Resultado(StrEnum):
    EXECUTAR = "executar"  # cabe na alçada: o agente executa sozinho
    PEDIR_APROVACAO = "pedir_aprovacao"  # acima da alçada: solicitar_aprovacao ao supervisor
    SINALIZAR_SUSPEITA = "sinalizar_suspeita"  # evidência incoerente: supervisor decide
    ESCALAR = "escalar"  # caso sensível ou sem regra: acionar_pessoa
    NEGAR = "negar"  # fora da política: negar_por_politica, citando a regra
    BLOQUEAR = "bloquear"  # violação (papel sem permissão, autoaprovação): não executa


class TipoSinal(StrEnum):
    HASH_REPETIDO = "hash_repetido"  # mesmo hash_perceptual em outro pedido (EC-16)
    CAPTURA_ANTES_DA_ENTREGA = (
        "captura_antes_da_entrega"  # exif_data_captura < data_entrega (EC-17)
    )
    EDITOR_DE_IMAGEM = "editor_de_imagem"  # exif_software preenchido
    PERSONALIZACAO_DIVERGENTE = "personalizacao_divergente"  # descrição ≠ texto do pedido (EC-18)
    PRODUTO_DIVERGENTE = "produto_divergente"  # descrição não bate com o SKU do pedido
    REENVIOS_ANTERIORES = "reenvios_anteriores"  # histórico do cliente (EC-19)
    SEM_EXIF = "sem_exif"  # informativo: sozinho NÃO é suspeita (EC-15)


@dataclass(frozen=True)
class Anexo:
    anexo_id: str
    conversation_id: str
    order_id: str | None
    hash_perceptual: str | None
    exif_data_captura: datetime | None
    exif_software: str | None
    descricao_visual: str


@dataclass(frozen=True)
class Item:
    item_id: str
    sku: str
    descricao: str
    tipo_item: str
    valor_total: float
    texto_personalizacao: str | None


@dataclass(frozen=True)
class Pedido:
    order_id: str
    customer_id: str
    marca: str
    valor: float
    status_entrega: str
    data_separacao: date | None
    data_entrega: date | None
    lote_produto: str | None
    itens: tuple[Item, ...] = ()


@dataclass(frozen=True)
class AcaoAnterior:
    """Ação com dinheiro já executada no pedido (`acoes_executadas_sistemas`)."""

    acao_id: str
    order_id: str
    acao: str  # nome da ferramenta: reenviar_produto, reembolsar, ...
    valor_rs: float
    executado_por: str
    aprovado_por: str | None


@dataclass(frozen=True)
class Sinal:
    tipo: TipoSinal
    descricao: str  # texto neutro, sem acusação, citando a evidência (anexo_id, datas)
    anexo_id: str | None = None


@dataclass(frozen=True)
class VeredictoEvidencia:
    """Saída de `atendimento.verificacao`."""

    suspeita: bool
    sinais: tuple[Sinal, ...]
    custo_aceitar_falso_rs: float  # valor do pedido × 45% (parametros.md)
    custo_sinalizar_verdadeiro_rs: float  # R$ 6 (parametros.md)
    justificativa: str


@dataclass(frozen=True)
class AcaoProposta:
    """O que o agente quer fazer. Quem decide se pode é `atendimento.politicas`."""

    ferramenta: str
    papel: Papel
    executado_por: str
    conversation_id: str | None = None
    order_id: str | None = None
    valor_rs: float = 0.0
    motivo: str = ""
    categoria: str | None = None  # avaria, item_faltante, reacao_adversa, ...
    aprovacao_id: str | None = None
    aprovado_por: str | None = None


@dataclass(frozen=True)
class Decisao:
    """Saída de `atendimento.politicas`."""

    resultado: Resultado
    regra: str  # chave de politicas.csv que fundamenta a decisão (ex.: limites_por_papel.atendente.reembolso_max_rs)
    motivo: str
    aprovador_sugerido: str | None = None  # colaborador_id do supervisor no turno (EC-22)
    acoes_obrigatorias: tuple[
        str, ...
    ] = ()  # ex.: orientar_suspensao_uso, registrar_cosmetovigilancia
    detalhes: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class RegistroAcao:
    """Linha gravada no log de ações dos sistemas simulados."""

    acao_id: str
    conversation_id: str | None
    order_id: str | None
    data_hora: datetime
    sistema: str
    acao: str
    valor_rs: float
    executado_por: str
    aprovado_por: str | None
    referencia_sistema: str
