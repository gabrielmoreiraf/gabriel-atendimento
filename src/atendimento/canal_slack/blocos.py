"""Mensagens do Canal do time em Block Kit (seção + contexto + botões quando pendente).

Block Kit: https://docs.slack.dev/reference/block-kit/blocks (section, context, actions) e
https://docs.slack.dev/reference/block-kit/block-elements/button-element.
"""

from __future__ import annotations

from atendimento.privacidade import mascarar

TITULOS = {
    "aprovacao": "Gabriel pediu aprovação",
    "suspeita": "Gabriel sinalizou uma suspeita",
    "escalacao": "Gabriel escalou um caso",
    "aviso": "Aviso do Gabriel",
}
BOTOES = {
    "aprovacao": (("fio_aprovar", "Aprovar", "primary"), ("fio_rejeitar", "Rejeitar", "danger")),
    "suspeita": (
        ("fio_procedente", "Procedente", "primary"),
        ("fio_improcedente", "Improcedente", "danger"),
    ),
}


def titulo(mensagem: dict) -> str:
    if mensagem.get("incidente_id"):
        return "Gabriel abriu um incidente"
    if mensagem.get("chave", "").startswith("aprovacao:"):
        return "Gabriel lembra uma aprovação parada"
    return TITULOS.get(mensagem.get("tipo", ""), "Gabriel")


def montar(mensagem: dict, *, pendente: bool, desfecho: str | None = None) -> tuple[str, list]:
    """(texto de fallback, blocos). Botões só em aprovação/suspeita pendente."""
    texto = mascarar(str(mensagem.get("texto", "")))
    cabecalho = titulo(mensagem)
    para = mensagem.get("para")
    principal = f"*{cabecalho}*" + (f" (para {para})" if para else "") + f"\n{texto}"
    blocos: list[dict] = [{"type": "section", "text": {"type": "mrkdwn", "text": principal}}]
    contexto = [mensagem.get("conversation_id"), mensagem.get("id")]
    blocos.append(
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": " · ".join(c for c in contexto if c)}],
        }
    )
    valor = mensagem.get("aprovacao_id") or mensagem.get("suspeita_id")
    tipo = "suspeita" if mensagem.get("suspeita_id") else "aprovacao"
    if pendente and valor and mensagem.get("tipo") in BOTOES:
        blocos.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "action_id": action_id,
                        "text": {"type": "plain_text", "text": rotulo},
                        "style": estilo,
                        "value": valor,
                    }
                    for action_id, rotulo, estilo in BOTOES[tipo]
                ],
            }
        )
    if desfecho:
        blocos.append(
            {"type": "context", "elements": [{"type": "mrkdwn", "text": mascarar(desfecho)}]}
        )
    fallback = f"{cabecalho}: {texto}" + (f" ({desfecho})" if desfecho else "")
    return mascarar(fallback), blocos
