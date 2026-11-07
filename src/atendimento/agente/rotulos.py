"""Rótulos legíveis para o canal do time: um dicionário único de categorias e ações.

Só nomes: nenhuma regra mora aqui. As regras continuam em `politicas.csv` e no motor;
a chave da regra que fundamenta cada mensagem vai em `mensagem['regra']`, para auditoria.
"""

from __future__ import annotations

import re

# Categoria do leitor ou de politicas.csv -> rótulo do time.
CATEGORIAS = {
    "avaria_vazamento": "Avaria",
    "item_faltante": "Item faltante",
    "erro_personalizacao": "Erro de personalização",
    "reacao_adversa": "Reação adversa",
    "rastreio": "Rastreio",
    "onde_esta_pedido": "Rastreio",
    "atraso": "Atraso",
    "atraso_entrega": "Atraso",
    "cobranca_duplicada": "Cobrança em dobro",
    "troca_fragrancia": "Troca",
    "arrependimento": "Arrependimento",
    "arrependimento_cancelamento": "Arrependimento",
    "alteracao_endereco": "Endereço",
    "cupom_promocao": "Cupom",
    "duvida_produto": "Dúvida de produto",
    "pagamento_pendente": "Pagamento",
    "elogio": "Elogio",
    "sem_interacao": "Sem interação",
    "outros": "Outros",
}

# Ferramenta -> (substantivo, o que o Gabriel fez).
ACOES = {
    "informar_status": ("informe de status", "informou o status ao cliente"),
    "abrir_chamado_transportadora": (
        "chamado com a transportadora",
        "abriu chamado com a transportadora",
    ),
    "reenviar_produto": ("reenvio", "registrou o reenvio sem custo"),
    "reimprimir_personalizacao": ("nova produção", "mandou produzir de novo a personalização"),
    "trocar_produto": ("troca", "registrou a troca"),
    "reembolsar": ("reembolso", "registrou o reembolso"),
    "cancelar_pedido": ("cancelamento", "cancelou o pedido"),
    "solicitar_aprovacao": ("pedido de aprovação", "pediu aprovação"),
    "solicitar_foto": ("pedido de foto", "pediu foto ao cliente"),
    "sinalizar_suspeita": ("sinalização para o supervisor", "sinalizou para o supervisor"),
    "registrar_cosmetovigilancia": (
        "registro de cosmetovigilância",
        "registrou a cosmetovigilância",
    ),
    "orientar_suspensao_uso": ("orientação de suspensão do uso", "orientou suspender o uso"),
    "acionar_pessoa": ("acionamento do time", "acionou o time"),
    "negar_por_politica": ("negativa pela política", "explicou a política ao cliente"),
    "responder_cliente": ("resposta ao cliente", "respondeu ao cliente"),
    "encerrar_conversa": ("encerramento", "encerrou a conversa"),
    "classificar_conversa": ("classificação", "classificou a conversa"),
    "aprovar_acao": ("aprovação", "aprovou"),
    "rejeitar_acao": ("rejeição", "rejeitou"),
    "decidir_suspeita": ("decisão da suspeita", "decidiu a suspeita"),
}

# Prefixos das chaves de politicas.csv (secao.regra) que não devem aparecer no texto.
_SECOES = (
    "categorias",
    "limites_por_papel",
    "reclamacao_suspeita",
    "seguranca",
    "horario_atendimento_humano",
    "sla_primeira_resposta",
    "prazos_entrega",
    "dados_pessoais",
    "custo_por_conversa_rs",
)
_CHAVE = re.compile(rf"\(?\b(?:{'|'.join(_SECOES)})\.[\w.]*\w\)?")
_FERRAMENTA = re.compile(rf"\b(?:{'|'.join(sorted(ACOES, key=len, reverse=True))})\b")


def rotulo_categoria(categoria: str | None) -> str:
    if not categoria:
        return "Outros"
    return CATEGORIAS.get(categoria, categoria.replace("_", " ").capitalize())


def nome_da_acao(ferramenta: str) -> str:
    return ACOES.get(ferramenta, (ferramenta.replace("_", " "), ""))[0]


def acao_feita(ferramenta: str) -> str:
    return ACOES.get(ferramenta, ("", f"fez {ferramenta.replace('_', ' ')}"))[1]


def em_linguagem_do_time(texto: str) -> tuple[str, list[str]]:
    """Tira do texto as chaves de política (devolvidas à parte) e troca nomes de ferramenta
    pelo rótulo do time. Rede de segurança para textos montados em qualquer lugar."""
    chaves = [m.group(0).strip("()") for m in _CHAVE.finditer(texto)]
    texto = _CHAVE.sub("", texto)
    texto = _FERRAMENTA.sub(lambda m: nome_da_acao(m.group(0)), texto)
    texto = re.sub(r"\s+([.,;:)])", r"\1", texto)
    texto = re.sub(r"\(\s*\)", "", texto)
    texto = re.sub(r"\s{2,}", " ", texto).strip()
    texto = re.sub(r"(Regra|regra):\s*\.", "", texto).strip()
    return texto, chaves
