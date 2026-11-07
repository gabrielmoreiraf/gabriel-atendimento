"""Leitor determinístico das mensagens do cliente (sem LLM: SPEC, decisão "LLM").

O leitor só *propõe* uma leitura (categoria, pedidos citados, sinais). Quem decide o que
fazer é o motor de políticas (HG-01). Texto do cliente é dado, nunca instrução (HG-09,
`politicas.csv`: seguranca.texto_do_cliente_e_dado_nao_instrucao).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from atendimento.privacidade import mascarar

__all__ = ["CATEGORIAS", "Leitura", "escolher_leitor", "ler", "mascarar"]

CATEGORIAS = (
    "avaria_vazamento",
    "item_faltante",
    "erro_personalizacao",
    "reacao_adversa",
    "rastreio",
    "atraso",
    "cobranca_duplicada",
    "troca_fragrancia",
    "arrependimento",
    "alteracao_endereco",
    "cupom_promocao",
    "duvida_produto",
    "elogio",
    "outros",
)


@dataclass(frozen=True)
class Leitura:
    categoria: str
    categoria_secundaria: str | None
    order_ids: tuple[str, ...]
    sensivel: bool  # reação adversa (HG-06)
    instrucao_embutida: bool  # texto tenta mandar no agente (HG-09)
    texto_mascarado: str  # CPF, cartão e telefone mascarados (HG-11)
    codigo_cupom: str | None = None  # código citado pelo cliente, para validar_cupom (EC-20)


# Ordem = prioridade: a primeira categoria encontrada é a principal.
# Padrões sobre o texto minúsculo e sem acento.
_PADROES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "reacao_adversa",
        re.compile(
            r"alergi|inchad|incha[cç]|inchar|inchou|ferid|coceira|cocando|irrita[cd]|ardencia|ardend|"
            r"manchas? vermelh|ficou vermelh|reacao (alergica|adversa|na pele)|"
            r"dor de barriga|vomit|bolinhas na pele"
        ),
    ),
    (
        "erro_personalizacao",
        re.compile(
            r"personaliza\w* (errad|diferent|torta|borrad)|nome de outra|nome errado|"
            r"saiu errad|escreveram|personaliza\w* .{0,40}(descasc|borr|apag)|"
            r"personaliza\w* que dura|iniciais? .{0,20}(tort|errad|borr|diferent)|"
            r"(saiu|sairam|ficou|ficaram) (torta|tortas|borrad)|pedi (as iniciais|o nome)"
        ),
    ),
    (
        "avaria_vazamento",
        re.compile(
            r"vazand|vazou|vazament|vazad|amassad|quebrad|riscad|danificad|avariad|rachad|trincad|"
            r"tampa (solta|abriu|aberta)|estourad|destruid|furad|rasgad|rasgo|vaozu"
        ),
    ),
    (
        "item_faltante",
        re.compile(
            r"(?<!\+ )brinde|faltou(?! o complemento)|faltando|faltava|incompleto|nao veio|veio so|chegou so|"
            r"metade do pedido|o que faltou|chegou (um|uma) so\b|unidades mas chegou"
        ),
    ),
    (
        "cobranca_duplicada",
        re.compile(
            r"cobra\w* (no|em|duas|2)\b.{0,30}tambem|cobra\w* .{0,30}tambem|"
            r"em dobro|duas vezes|duplicad|cobrado 2x|cobraram 2x"
        ),
    ),
    (
        "atraso",
        re.compile(
            r"atrasad|atraso|pra ter chegado|para ter chegado|prazo (venceu|era|ja venceu)|"
            r"prometeram entregar|ainda nao chegou|nao chegou|nao recebi|prazo .{0,20}venc|"
            r"nao entregue"
        ),
    ),
    (
        "rastreio",
        re.compile(
            r"rastreio|rastreamento|onde esta meu pedido|onde esta o meu pedido|"
            r"aguardando transferencia|em transferencia|nao andou|vai chegar quando|"
            r"parado no centro|"
            # HG-18: frases de rastreio do histórico que caíam em "outros"
            r"em transito|(esta|ta|ficou) parad|parado (em|no|na|desde)|"
            r"status do (meu )?pedido|cade (o )?meu pedido|previsao de entrega|"
            r"ja foi enviad|nao atualiza|sem atualiza"
        ),
    ),
    # HG-18: nomes de `politicas.csv` (categorias.troca_fragrancia). Antes de arrependimento:
    # "não gostei do cheiro, posso trocar?" é troca, não desistência.
    (
        "troca_fragrancia",
        re.compile(
            r"(posso|quero|gostaria de|da pra|da para) trocar(?! o (endereco|numero|cep))|"
            r"trocar (por|pela|pelo) (outr|um |uma )|troca de (fragrancia|perfume|cheiro)|"
            r"trocar a fragrancia|nao combinou|nao gostei (do|da) (cheiro|fragrancia|perfume)|"
            r"(cheiro|fragrancia) .{0,40}diferente do que|nao fixa|prefiro (a|o) de"
        ),
    ),
    (
        "arrependimento",
        re.compile(
            r"devolver|devolucao|nao gostei|desisti|arrependi|cancelar o pedido|"
            r"quero cancelar|dinheiro de volta"
        ),
    ),
    # HG-18: categorias.alteracao_endereco
    (
        "alteracao_endereco",
        re.compile(
            r"(atualizar|alterar|mudar|trocar|corrigir|corrijo|incluir)\b.{0,40}"
            r"(endereco|\bcep\b|nome da rua|numero da casa|complemento)|"
            r"(endereco|\bcep\b) .{0,20}(errad|incorret|desatualizad)|me mudei|"
            r"complemento no endereco|nome da rua|numero da casa|entreg\w* no endereco"
        ),
    ),
    # EC-20: nomes de `politicas.csv` (categorias.cupom_promocao, categorias.duvida_produto).
    # Prioridade mais baixa: numa reclamação com pergunta, a reclamação é a principal.
    (
        "cupom_promocao",
        re.compile(
            r"\bcupo(m|ns)\b|codigo (de desconto|promocional)|black friday|frete gratis|"
            r"desconto (nao|so) (aplic|funcion|entrou|valeu)|nao (aplicou|deu|entrou) o desconto"
        ),
    ),
    (
        "duvida_produto",
        re.compile(
            r"(pode|posso|da pra|da para|consigo) (se )?usar|serve (pra|para)|vegan|cruelty|"
            r"por quanto tempo|quanto tempo (dura|mantem)|mantem (gelad|quent)|"
            r"como (eu )?(uso|usar|aplic|lav)|e indicad|tem (cheiro|fragrancia|perfume)|"
            r"qual a diferenca|vaza se|e original|qual (o )?tamanho|e hipoalergenic|"
            r"tem (gluten|lactose|parabeno)"
        ),
    ),
    # HG-18: categorias.elogio. Prioridade mais baixa: elogio com reclamação é reclamação.
    (
        "elogio",
        re.compile(
            r"elogi|parabens|\bamei\b|\badorei\b|bem embalad|veio tudo (perfeito|certinho)|"
            r"ficou lind|super atencios|chegou rapidinho|entrega (foi )?super rapida"
        ),
    ),
)

_ORDER_ID = re.compile(r"\b(G[BC]H\d{6})\b")
# Sem a lista de `cupons.csv`: só o código em maiúsculas logo depois de "cupom"/"código".
_CUPOM_CITADO = re.compile(
    r"(?i:\b(?:cupom|cupons|cupon|c[oó]digo)\b)\s+"
    r"(?:(?i:de desconto|promocional)\s+)?([A-Z][A-Z0-9]{3,19})\b"
)

_INSTRUCAO = re.compile(
    r"ignor\w+ (todas )?(as )?(suas )?(instrucoes|regras|ordens)|"
    r"(instrucao|instrucoes|obs|nota|recado|aviso|mensagem)\s+(para|pro|pra|ao|a)\s+"
    r"(o |a )?(assistente|robo|bot|agente|ia|sistema|modelo)|"
    r"(assistente virtual|robo|agente|bot|sistema)\s*:\s*\w|"
    r"voce (agora )?e um (assistente|robo|agente)|"
    r"aprove o (reembolso|estorno)|libere o (reembolso|estorno|reenvio)"
)


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return sem_acento.lower()


def _codigo_cupom(texto: str, normal: str, cupons) -> str | None:
    """Com `cupons` (códigos de `cupons.csv`), devolve o primeiro citado, na grafia do cadastro;
    sem a lista, o código em maiúsculas logo depois de "cupom"/"código". Nunca inventa."""
    if cupons is not None:
        achados = []
        for codigo in cupons:
            m = re.search(rf"\b{re.escape(codigo.lower())}\b", normal)
            if m:
                achados.append((m.start(), -len(codigo), codigo))
        return min(achados)[2] if achados else None
    for m in _CUPOM_CITADO.finditer(texto):
        if not _ORDER_ID.fullmatch(m.group(1)):
            return m.group(1)
    return None


def ler(texto: str, *, cupons=None) -> Leitura:
    """`cupons`: códigos válidos (`cupons.csv`, coluna `codigo`) para achar o cupom citado."""
    normal = _normalizar(texto)
    achadas = [nome for nome, padrao in _PADROES if padrao.search(normal)]
    if achadas[:1] in (["atraso"], ["rastreio"]):
        # "se não chegar, quero o dinheiro de volta" é condição do atraso, não outra demanda
        achadas = [c for c in achadas if c != "arrependimento"]
    categoria = achadas[0] if achadas else "outros"
    secundaria = achadas[1] if len(achadas) > 1 else None
    order_ids = tuple(dict.fromkeys(_ORDER_ID.findall(texto.upper())))
    return Leitura(
        categoria=categoria,
        categoria_secundaria=secundaria,
        order_ids=order_ids,
        sensivel=categoria == "reacao_adversa",
        instrucao_embutida=bool(_INSTRUCAO.search(normal)),
        texto_mascarado=mascarar(texto),
        codigo_cupom=_codigo_cupom(texto, normal, cupons),
    )


def escolher_leitor(*, carregar_env: bool = True):
    """Ponto de escolha do leitor: `ATENDIMENTO_LLM=1` liga o leitor com Claude
    (`leitor_claude.LeitorClaude`); ausente ou `0`, o leitor por regras (`ler`, o padrão).
    Carrega `.env` com python-dotenv; o valor da chave nunca é lido aqui."""
    import os

    if carregar_env:
        from dotenv import load_dotenv

        load_dotenv()
    if os.environ.get("ATENDIMENTO_LLM", "0").strip() != "1":
        return ler
    from pathlib import Path

    from atendimento.agente.leitor_claude import LeitorClaude

    raiz = Path(__file__).resolve().parents[3]
    return LeitorClaude(cache=raiz / "var" / "cache_leitor_claude")
