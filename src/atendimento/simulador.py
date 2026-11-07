"""Simulador de WhatsApp da demo: o cliente escreve e a mensagem entra na fila como uma conversa
nova, que o Gabriel trata pelo fluxo de sempre (leitor, pedido por ID, política, ferramentas).

O cliente é identificado pelo cadastro (`customer_id`), como faria o número do WhatsApp; o
pedido vem do próprio cadastro. O canal real (WhatsApp Business) fica para integração futura:
aqui só muda de onde a mensagem chega, não como o agente decide.
"""

from __future__ import annotations

from datetime import timedelta

from atendimento.privacidade import mascarar

PREFIXO = "WPP-"
_FORMATO = "%Y-%m-%d %H:%M:%S"


def _nome_mascarado(nome: str | None) -> str:
    """HG-11: o nome completo nunca sai; vira "Primeiro S."."""
    nome = (nome or "").strip()
    return mascarar(nome, nomes=(nome,)) if nome else "Cliente"


def clientes_demo(base, limite: int = 8) -> list[dict]:
    """Clientes da fila do dia que têm pedido (contexto real da base), com os pedidos mais
    recentes de cada um. Completa com outros clientes com pedido se a fila tiver poucos."""
    ids: list[str] = []
    for linha in base.banco.executar(
        "SELECT customer_id FROM fila_aberta WHERE order_id IS NOT NULL AND order_id <> '' "
        "ORDER BY data_abertura, conversation_id"
    ):
        if linha["customer_id"] not in ids and not str(linha["customer_id"]).startswith(PREFIXO):
            ids.append(linha["customer_id"])
    if len(ids) < limite:
        for linha in base.banco.executar(
            "SELECT DISTINCT customer_id FROM pedidos ORDER BY customer_id LIMIT ?", (limite * 2,)
        ):
            if linha["customer_id"] not in ids:
                ids.append(linha["customer_id"])
    clientes = []
    for customer_id in ids[:limite]:
        cadastro = base.banco.executar_um(
            "SELECT nome FROM clientes WHERE customer_id = ?", (customer_id,)
        )
        if cadastro is None:
            continue
        pedidos = base.banco.executar(
            "SELECT order_id, marca, status_entrega, valor, descricao_produto FROM pedidos "
            "WHERE customer_id = ? ORDER BY data_pedido DESC, order_id LIMIT 3",
            (customer_id,),
        )
        clientes.append(
            {
                "customer_id": customer_id,
                "nome": _nome_mascarado(cadastro.get("nome")),
                "pedidos": [_pedido(p) for p in pedidos],
            }
        )
    return clientes


def _pedido(linha) -> dict:
    pedido = dict(linha)
    try:  # a base guarda o valor como texto; a tela formata número
        pedido["valor"] = float(pedido["valor"]) if pedido.get("valor") not in (None, "") else None
    except (TypeError, ValueError):
        pedido["valor"] = None
    return pedido


def _proximo_id(base) -> str:
    linha = base.banco.executar_um(
        "SELECT COUNT(*) AS n FROM fila_aberta WHERE conversation_id LIKE ?", (f"{PREFIXO}%",)
    )
    return f"{PREFIXO}{int(linha['n']) + 1:04d}"


def receber_mensagem(
    agente, customer_id: str, texto: str, order_id: str | None = None, anterior: str | None = None
) -> dict:
    """Grava a mensagem como uma conversa nova na fila e processa com o agente.
    KeyError se o cliente ou o pedido não forem dele."""
    base = agente.base
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("mensagem vazia")
    if (
        base.banco.executar_um("SELECT 1 AS ok FROM clientes WHERE customer_id = ?", (customer_id,))
        is None
    ):
        raise KeyError(customer_id)
    pedido = base.banco.executar_um(
        "SELECT order_id, marca FROM pedidos WHERE customer_id = ? "
        + ("AND order_id = ? " if order_id else "")
        + "ORDER BY data_pedido DESC LIMIT 1",
        (customer_id, order_id) if order_id else (customer_id,),
    )
    if order_id and pedido is None:
        raise KeyError(order_id)

    # Cada mensagem do WhatsApp é um atendimento novo, decidido pelo que o cliente disse
    # agora: juntar o histórico fazia o leitor responder de novo a pergunta antiga. O chat
    # da tela guarda a conversa inteira; `anterior` fica só como referência da sequência.
    del anterior
    historico: list[tuple[str, str]] = []
    historico.append(("cliente", texto))

    cid = _proximo_id(base)
    abertura = agente.agora
    with base.banco.transacao():
        base.banco.executar(
            "INSERT INTO fila_aberta (conversation_id, customer_id, order_id, marca, canal, "
            "data_abertura, status, n_interacoes, atendente_id, data_primeira_resposta, assunto) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                cid,
                customer_id,
                pedido["order_id"] if pedido else "",
                pedido["marca"] if pedido else "",
                "whatsapp",
                abertura.strftime(_FORMATO),
                "aberta",
                str(len(historico)),
                "",
                "",
                "",
            ),
        )
        for i, (autor, conteudo) in enumerate(historico):
            base.banco.executar(
                "INSERT INTO historico_mensagens (conversation_id, message_id, autor, timestamp, "
                "texto) VALUES (?, ?, ?, ?, ?)",
                (
                    cid,
                    f"{cid}-{i + 1:02d}",
                    autor,
                    (abertura + timedelta(seconds=i)).strftime(_FORMATO),
                    conteudo,
                ),
            )

    caso = agente.processar(cid)
    return {
        "conversation_id": cid,
        "resposta": caso.resposta_ao_cliente,
        "estado": caso.estado,
        "categoria": caso.categoria,
        "mensagens": [{"autor": m["autor"], "texto": m["texto"]} for m in base.mensagens(cid)],
    }
