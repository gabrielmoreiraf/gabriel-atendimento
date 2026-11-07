"""HG-18: acerto de categoria do leitor do agente contra a `tag_agente` humana.

Usa `atendimento.agente.leitor.ler` só para leitura, sobre as mensagens do cliente de cada
conversa (o mesmo texto que o agente lê). A categoria do leitor vira tag pela
`politicas.categorias.<categoria>.tag_equivalente`.
"""

from __future__ import annotations

from dataclasses import dataclass

from atendimento.agente.leitor import ler

# Nome da categoria no leitor -> nome em politicas.csv, quando difere.
LEITOR_PARA_POLITICA = {
    "rastreio": "onde_esta_pedido",
    "atraso": "atraso_entrega",
    "arrependimento": "arrependimento_cancelamento",
}
# Categorias sem tag_equivalente (erro_personalizacao, reacao_adversa) aparecem no histórico
# como "Reclamação produto", a tag de `politicas.tags_agente` para reclamação do produto.
TAG_SEM_EQUIVALENTE = "Reclamação produto"
SEM_INTERACAO = "sem_interacao"


@dataclass(frozen=True)
class LinhaCategoria:
    conversation_id: str
    tag_agente: str
    categoria: str  # do leitor; sem_interacao quando o cliente não escreveu
    tag_prevista: str | None
    acertou: bool | None  # None = sem mensagem do cliente (fora da conta)


def tag_da_categoria(categoria: str, politicas: dict[str, str]) -> str:
    if categoria == "outros":
        return "Outros"
    nome = LEITOR_PARA_POLITICA.get(categoria, categoria)
    tag = politicas.get(f"categorias.{nome}.tag_equivalente", "")
    return tag or TAG_SEM_EQUIVALENTE


def acerto_categoria(
    conversas: dict[str, dict],
    mensagens_do_cliente: dict[str, list[str]],
    politicas: dict[str, str],
) -> list[LinhaCategoria]:
    linhas = []
    for cid, conversa in sorted(conversas.items()):
        textos = [t for t in mensagens_do_cliente.get(cid, []) if t and t.strip()]
        if not textos:
            linhas.append(LinhaCategoria(cid, conversa["tag_agente"], SEM_INTERACAO, None, None))
            continue
        categoria = ler("\n".join(textos)).categoria
        prevista = tag_da_categoria(categoria, politicas)
        linhas.append(
            LinhaCategoria(
                conversation_id=cid,
                tag_agente=conversa["tag_agente"],
                categoria=categoria,
                tag_prevista=prevista,
                acertou=prevista == conversa["tag_agente"],
            )
        )
    return linhas


def piores_categorias(
    linhas: list[LinhaCategoria], quantas: int = 3
) -> list[tuple[str, int, int, float]]:
    """Tags humanas com menor acerto: (tag, conversas, acertos, fração), da pior para a melhor.
    Empate no acerto: a tag com mais conversas vem antes."""
    por_tag: dict[str, list[bool]] = {}
    for linha in linhas:
        if linha.acertou is not None:
            por_tag.setdefault(linha.tag_agente, []).append(linha.acertou)
    ordem = sorted(
        ((tag, len(v), sum(v), sum(v) / len(v)) for tag, v in por_tag.items()),
        key=lambda t: (t[3], -t[1], t[0]),
    )
    return ordem[:quantas]


# Critério de "escalação humana" no histórico (acoes_executadas_sistemas): a conversa teve
# registrar_cosmetovigilancia (feito por supervisor) ou alguma ação com aprovado_por.
# O histórico não registra acionar_pessoa, então esse é o sinal disponível de que uma
# pessoa acima do atendente entrou no caso.
def escalacoes_corretas(sensiveis_leitor: set[str], acoes: list[dict]) -> dict[str, int]:
    escaladas = {
        a["conversation_id"]
        for a in acoes
        if a["acao"] == "registrar_cosmetovigilancia" or a.get("aprovado_por")
    }
    cosmeto = {a["conversation_id"] for a in acoes if a["acao"] == "registrar_cosmetovigilancia"}
    return {
        "sensiveis_leitor": len(sensiveis_leitor),
        "com_escalacao_humana": len(sensiveis_leitor & escaladas),
        "cosmetovigilancia_humana": len(cosmeto),
        "cosmetovigilancia_vista_pelo_leitor": len(cosmeto & sensiveis_leitor),
    }
