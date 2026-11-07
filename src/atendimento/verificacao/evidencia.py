"""Verificador de evidência: "a reclamação procede?" (EC-15..EC-19, Q15, HG-07).

Código puro, sem I/O: recebe `Pedido` e `Anexo` prontos (montados por `atendimento.dados`)
e devolve um `VeredictoEvidencia`. Os textos citam fatos (anexo_id, datas, pedidos) e
nunca acusam o cliente (`politicas.csv`, `reclamacao_suspeita.comunicacao_com_cliente`).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime

from atendimento.contratos import AGORA, Anexo, Pedido, Sinal, TipoSinal, VeredictoEvidencia

# docs/parametros.md, seção "Reclamações que não procedem":
#   reenviar/reembolsar uma reclamação que não procede = valor do pedido × 45%
#   sinalizar para o supervisor uma reclamação verdadeira = R$ 6
FATOR_CUSTO_ACEITAR_FALSO = 0.45
CUSTO_SINALIZAR_VERDADEIRO_RS = 6.0

# EC-19. Consulta em docs/trocas_reenvios.csv (UTF-8, separador ","), tipo == "reenvio",
# contando linhas por customer_id:
#   1 reenvio: 294 clientes; 2: 96; 3: 13; 4: 4  (407 clientes com reenvio, de 2.867 em clientes.csv)
# Contando todos os tipos (reenvio, troca, nova_producao): 1: 386; 2: 109; 3: 13; 4: 6.
# Até 2 reenvios é comum (p95 dos clientes com reenvio = 2); 3 ou mais é a cauda (17 clientes,
# 4,2% de quem já teve reenvio). O sinal é registrado a partir de 1 reenvio (Q15, EC-19);
# o limiar só muda o texto da descrição ("acima do comum").
LIMIAR_REENVIOS = 2

# Q15 (SPEC.md): só sinais fortes tornam o caso suspeito.
SINAIS_FORTES = frozenset(
    {TipoSinal.HASH_REPETIDO, TipoSinal.CAPTURA_ANTES_DA_ENTREGA, TipoSinal.EDITOR_DE_IMAGEM}
)
# Sinais de contexto: registrados como evidência, mas nunca tornam o caso suspeito.
# SEM_EXIF: WhatsApp remove metadados (politicas.csv, reclamacao_suspeita.observacao) (EC-15).
# REENVIOS_ANTERIORES: histórico é evidência adicional, não basta sozinho (EC-19).
# PERSONALIZACAO_DIVERGENTE: o agente (W4) pede nova foto antes de decidir; em
#   erro_personalizacao a divergência confirma a reclamação (EC-18).
SINAIS_DE_CONTEXTO = frozenset(
    {TipoSinal.SEM_EXIF, TipoSinal.REENVIOS_ANTERIORES, TipoSinal.PERSONALIZACAO_DIVERGENTE}
)

# Texto impresso citado na descrição visual: entre aspas duplas, ou nome/iniciais/texto seguido
# de palavra iniciada em maiúscula ("o nome Ana impresso"). Palavras-chave em minúscula de
# propósito: "Personalizada Nome com..." é o nome do produto, não um texto citado.
_CITADO_ENTRE_ASPAS = re.compile(r"[\"“”]([^\"“”]{1,40})[\"“”]")
_CITADO_APOS_PALAVRA = re.compile(
    r"\b(?:nome|iniciais|texto|escrito)\s+([A-ZÀ-Ý][\wÀ-ÿ.]*(?:\s+[A-ZÀ-Ý][\wÀ-ÿ.]*)*)"
)


def _br(d: date | datetime) -> str:
    return d.strftime("%d/%m/%Y %H:%M") if isinstance(d, datetime) else d.strftime("%d/%m/%Y")


def _rs(valor: float) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", sem_acento.casefold())


def _textos_citados(descricao: str) -> list[str]:
    citados = _CITADO_ENTRE_ASPAS.findall(descricao)
    if not citados:
        citados = _CITADO_APOS_PALAVRA.findall(descricao)
    # `20" Personalizada ... "` (polegadas) não é texto citado: aspas coladas ao texto.
    return [c for c in citados if c == c.strip() and _normalizar(c)]


def _sinais_do_anexo(
    anexo: Anexo, pedido: Pedido, mesmo_hash: list[Anexo], textos_pedido: list[str]
) -> list[Sinal]:
    sinais: list[Sinal] = []
    aid = anexo.anexo_id

    if anexo.exif_data_captura is None:
        sinais.append(
            Sinal(
                TipoSinal.SEM_EXIF,
                f"O anexo {aid} chegou sem data de captura nos metadados (comum em fotos "
                "enviadas pelo WhatsApp); informação apenas de contexto.",
                aid,
            )
        )
    elif pedido.data_entrega and anexo.exif_data_captura.date() < pedido.data_entrega:
        sinais.append(
            Sinal(
                TipoSinal.CAPTURA_ANTES_DA_ENTREGA,
                f"O anexo {aid} registra captura em {_br(anexo.exif_data_captura)}, anterior "
                f"à entrega do pedido {pedido.order_id} em {_br(pedido.data_entrega)}.",
                aid,
            )
        )

    if anexo.exif_software:
        sinais.append(
            Sinal(
                TipoSinal.EDITOR_DE_IMAGEM,
                f'Os metadados do anexo {aid} indicam edição no software "{anexo.exif_software}".',
                aid,
            )
        )

    outros_pedidos = sorted(
        {
            a.order_id
            for a in mesmo_hash
            if a.anexo_id != aid and a.order_id and a.order_id != pedido.order_id
        }
    )
    if outros_pedidos:
        outros_anexos = sorted(a.anexo_id for a in mesmo_hash if a.order_id in set(outros_pedidos))
        sinais.append(
            Sinal(
                TipoSinal.HASH_REPETIDO,
                f"O anexo {aid} (pedido {pedido.order_id}) tem o mesmo hash perceptual "
                f"{anexo.hash_perceptual} do(s) anexo(s) {', '.join(outros_anexos)}, "
                f"enviado(s) para o(s) pedido(s) {', '.join(outros_pedidos)}.",
                aid,
            )
        )

    if textos_pedido:
        citados = _textos_citados(anexo.descricao_visual)
        esperados = {_normalizar(t) for t in textos_pedido}
        divergentes = [c for c in citados if _normalizar(c) not in esperados]
        if citados and len(divergentes) == len(citados):
            sinais.append(
                Sinal(
                    TipoSinal.PERSONALIZACAO_DIVERGENTE,
                    f"A descrição do anexo {aid} mostra o texto "
                    f"{', '.join(repr(c) for c in divergentes)}, diferente da personalização "
                    f"registrada no pedido {pedido.order_id} "
                    f"({', '.join(repr(t) for t in textos_pedido)}). Vale pedir nova foto.",
                    aid,
                )
            )
    return sinais


def verificar(
    *,
    pedido: Pedido,
    anexos: list[Anexo],
    anexos_mesmo_hash: dict[str, list[Anexo]],
    reenvios_anteriores_cliente: int,
    agora: datetime = AGORA,
) -> VeredictoEvidencia:
    """Confere a evidência da reclamação contra o pedido e o histórico.

    `anexos_mesmo_hash`: para cada hash dos anexos da conversa, todos os anexos da base
    com o mesmo hash (inclusive o próprio). `reenvios_anteriores_cliente`: quantidade de
    linhas de `trocas_reenvios.csv` com o `customer_id` do pedido e `tipo == "reenvio"`
    (trocas e novas produções não contam). A partir de 1, gera `REENVIOS_ANTERIORES`; acima
    de `LIMIAR_REENVIOS`, a descrição diz "acima do comum". `agora` fica na assinatura para o
    contrato não depender do relógio; as regras atuais usam só as datas dos dados.

    Suspeita (Q15) = existe sinal forte (`SINAIS_FORTES`) e o custo de aceitar uma
    reclamação que não procede (valor × 45%) supera o de sinalizar (R$ 6). Sinais de
    contexto (`SINAIS_DE_CONTEXTO`) entram na evidência, mas nunca tornam o caso suspeito.
    """
    del agora  # nenhuma regra atual depende do "agora"; nunca usar o relógio do sistema
    textos_pedido = [i.texto_personalizacao for i in pedido.itens if i.texto_personalizacao]

    sinais: list[Sinal] = []
    for anexo in anexos:
        mesmo_hash = anexos_mesmo_hash.get(anexo.hash_perceptual or "", [])
        sinais.extend(_sinais_do_anexo(anexo, pedido, mesmo_hash, textos_pedido))

    if reenvios_anteriores_cliente >= 1:
        n = reenvios_anteriores_cliente
        comum = f", acima do comum na base (até {LIMIAR_REENVIOS})" if n > LIMIAR_REENVIOS else ""
        sinais.append(
            Sinal(
                TipoSinal.REENVIOS_ANTERIORES,
                f"O cliente {pedido.customer_id} tem {n} {'reenvio' if n == 1 else 'reenvios'} "
                f"anterior{'' if n == 1 else 'es'} registrado{'' if n == 1 else 's'}{comum}; "
                "evidência adicional, não decisiva sozinha.",
            )
        )

    custo_aceitar = round(pedido.valor * FATOR_CUSTO_ACEITAR_FALSO, 2)
    fortes = [s for s in sinais if s.tipo in SINAIS_FORTES]
    custo_compensa = custo_aceitar > CUSTO_SINALIZAR_VERDADEIRO_RS
    suspeita = bool(fortes) and custo_compensa

    return VeredictoEvidencia(
        suspeita=suspeita,
        sinais=tuple(sinais),
        custo_aceitar_falso_rs=custo_aceitar,
        custo_sinalizar_verdadeiro_rs=CUSTO_SINALIZAR_VERDADEIRO_RS,
        justificativa=_justificativa(pedido, anexos, sinais, fortes, suspeita, custo_aceitar),
    )


def _justificativa(
    pedido: Pedido,
    anexos: list[Anexo],
    sinais: list[Sinal],
    fortes: list[Sinal],
    suspeita: bool,
    custo_aceitar: float,
) -> str:
    ids = ", ".join(a.anexo_id for a in anexos) or "nenhum anexo"
    base = f"Pedido {pedido.order_id}; anexos avaliados: {ids}."
    custos = (
        f"Custo de aceitar uma reclamação que não procede: {_rs(custo_aceitar)} "
        f"(45% de {_rs(pedido.valor)}); custo de levar ao supervisor: "
        f"{_rs(CUSTO_SINALIZAR_VERDADEIRO_RS)}."
    )
    fatos = " ".join(s.descricao for s in sinais)
    if suspeita:
        conclusao = (
            "Há fatos verificáveis que não batem com o pedido: o caso vai para análise do "
            "supervisor antes de reenvio, troca ou reembolso."
        )
    elif fortes:
        conclusao = (
            "Há fatos verificáveis que não batem com o pedido, mas o valor não justifica "
            "levar ao supervisor: segue a política normal."
        )
    else:
        conclusao = (
            "Nenhum sinal forte (imagem repetida, captura antes da entrega ou edição): "
            "segue a política normal."
        )
    return " ".join(p for p in (base, fatos, custos, conclusao) if p)
