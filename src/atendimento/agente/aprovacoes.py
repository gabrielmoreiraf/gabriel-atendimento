"""Aprovar ou rejeitar uma ação pendente pelo canal do time (HP-10, HG-03).

Só supervisor decide; ninguém aprova a própria ação (`politicas.csv`:
limites_por_papel.supervisor.nao_aprova_a_propria_acao). A ação aprovada passa de novo pelo
motor de políticas (HG-01) com `aprovacao_id` e `aprovado_por` antes de ser executada.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from atendimento.agente.rotulos import nome_da_acao
from atendimento.contratos import AcaoProposta, Papel, Resultado
from atendimento.politicas import decidir

if TYPE_CHECKING:
    from atendimento.agente.caso import Agente, Caso


def _rs(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class AprovacaoRecusada(Exception):
    """Pedido de aprovar/rejeitar que fere a política (autoaprovação, papel, estado)."""


class AprovacaoInvalida(Exception):
    """Ação com `aprovacao_id` que a aprovação registrada não cobre (HG-05, Q21)."""


def validar_aprovacao(aprovacao: dict | None, acao: AcaoProposta, equipe: list[dict]) -> str | None:
    """Q21: o agente confere o `aprovacao_id` antes de executar (o motor confia no que recebe).

    Devolve o motivo da recusa, ou None se a aprovação cobre a ação: existe, está aprovada,
    foi decidida por supervisor ativo diferente do solicitante, mesma ferramenta, mesmo
    pedido e valor menor ou igual ao aprovado.
    """
    if aprovacao is None:
        return f"aprovação {acao.aprovacao_id} não existe"
    if aprovacao.get("estado") != "aprovada":
        return f"aprovação {acao.aprovacao_id} está {aprovacao.get('estado')}, não aprovada"
    decidido_por = aprovacao.get("decidido_por")
    ativos = {
        c["colaborador_id"]
        for c in equipe
        if c.get("cargo") == "supervisor" and c.get("status", "ativo") == "ativo"
    }
    if decidido_por not in ativos:
        return f"{decidido_por} não é supervisor ativo"
    if decidido_por == aprovacao.get("solicitado_por"):
        return (
            "decidida por quem solicitou (limites_por_papel.supervisor.nao_aprova_a_propria_acao)"
        )
    if acao.aprovado_por and acao.aprovado_por != decidido_por:
        return f"aprovado_por {acao.aprovado_por} difere de quem decidiu ({decidido_por})"
    aprovada: AcaoProposta = aprovacao["acao"]
    if aprovada.ferramenta != acao.ferramenta:
        return f"aprovação cobre {aprovada.ferramenta}, não {acao.ferramenta}"
    if aprovada.order_id != acao.order_id:
        return f"aprovação cobre o pedido {aprovada.order_id}, não {acao.order_id}"
    if acao.valor_rs > aprovada.valor_rs + 1e-9:
        return f"valor R$ {acao.valor_rs:.2f} acima do aprovado (R$ {aprovada.valor_rs:.2f})"
    return None


@dataclass
class Aprovacao:
    aprovacao_id: str
    acao: AcaoProposta
    solicitado_por: str
    aprovador_sugerido: str | None
    estado: str = "pendente"  # pendente, aprovada, rejeitada
    decidido_por: str | None = None
    comentario: str = ""


def _pendente(agente: Agente, aprovacao_id: str, supervisor_id: str) -> Aprovacao:
    aprovacao = agente.aprovacoes.get(aprovacao_id)
    if aprovacao is None:
        raise KeyError(aprovacao_id)
    if aprovacao.estado != "pendente":
        raise AprovacaoRecusada(f"Aprovação {aprovacao_id} já está {aprovacao.estado}.")
    cargo = {c["colaborador_id"]: c.get("cargo") for c in agente.equipe}.get(supervisor_id)
    if cargo != "supervisor":
        raise AprovacaoRecusada(f"{supervisor_id} não é supervisor: não pode decidir aprovações.")
    if supervisor_id in (aprovacao.solicitado_por, aprovacao.acao.executado_por):
        raise AprovacaoRecusada(
            "O supervisor não aprova a própria ação "
            "(limites_por_papel.supervisor.nao_aprova_a_propria_acao)."
        )
    return aprovacao


def _ato_do_supervisor(ferramenta: str, aprovacao: Aprovacao, supervisor_id: str, texto: str):
    return AcaoProposta(
        ferramenta=ferramenta,
        papel=Papel.SUPERVISOR,
        executado_por=supervisor_id,
        conversation_id=aprovacao.acao.conversation_id,
        order_id=aprovacao.acao.order_id,
        aprovacao_id=aprovacao.aprovacao_id,
        motivo=texto,
    )


def _fechar_no_canal(agente: Agente, aprovacao: Aprovacao) -> None:
    for mensagem in agente.canal:
        if mensagem.get("aprovacao_id") == aprovacao.aprovacao_id:
            mensagem["estado"] = aprovacao.estado
    agente.emitir(
        "aprovacao",
        {
            "aprovacao_id": aprovacao.aprovacao_id,
            "estado": aprovacao.estado,
            "decidido_por": aprovacao.decidido_por,
            "conversation_id": aprovacao.acao.conversation_id,
        },
    )


def _atualizar_estado(agente: Agente, caso: Caso) -> None:
    ainda_pendente = any(agente.aprovacoes[a].estado == "pendente" for a in caso.aprovacao_ids)
    if caso.estado == "aguardando_aprovacao" and not ainda_pendente:
        caso.estado = "resolvida"
    agente.emitir("caso", agente.resumo(caso))


def aprovar(agente: Agente, aprovacao_id: str, supervisor_id: str, comentario: str = "") -> Caso:
    aprovacao = _pendente(agente, aprovacao_id, supervisor_id)
    acao = replace(aprovacao.acao, aprovacao_id=aprovacao_id, aprovado_por=supervisor_id)
    caso = agente.casos[acao.conversation_id]
    # HG-03 / Q21: valida e decide ANTES de gravar "aprovada"; se algo falha, fica pendente.
    registrada = agente.ferramentas.aprovacao(aprovacao_id)
    if registrada is None or registrada.get("estado") != "pendente":
        raise AprovacaoRecusada(f"Aprovação {aprovacao_id} não está pendente no sistema.")
    simulada = {**registrada, "estado": "aprovada", "decidido_por": supervisor_id}
    motivo = validar_aprovacao(simulada, acao, agente.equipe)
    if motivo:
        raise AprovacaoRecusada(motivo)
    pedido = agente.base.pedido(acao.order_id) if acao.order_id else None
    decisao = decidir(
        acao,
        pedido=pedido,
        acoes_anteriores=agente._acoes_anteriores(acao.order_id),
        politicas=agente.politicas,
        equipe=agente.equipe,
        agora=agente.agora,
    )
    if decisao.resultado is not Resultado.EXECUTAR:
        raise AprovacaoRecusada(f"Política não libera a ação aprovada: {decisao.motivo}")
    agente.executar(caso, _ato_do_supervisor("aprovar_acao", aprovacao, supervisor_id, comentario))
    registro = agente.executar(caso, acao)
    if "coleta_reversa" in decisao.acoes_obrigatorias:
        agente.pedir_coleta_reversa(caso, acao)
    caso.decisoes.append(decisao)
    aprovacao.estado, aprovacao.decidido_por, aprovacao.comentario = (
        "aprovada",
        supervisor_id,
        comentario,
    )
    _fechar_no_canal(agente, aprovacao)
    agente.postar_no_canal(
        "aviso",
        supervisor_id,
        f"{caso.conversation_id}: {nome_da_acao(acao.ferramenta)} de {_rs(acao.valor_rs)} "
        f"aprovado por {supervisor_id} e feito pelo FIO (ref. {registro.referencia_sistema}).",
        caso.conversation_id,
        aprovacao_id=aprovacao_id,
    )
    from atendimento.agente.caso import _texto_executado

    texto = _texto_executado(acao, registro)
    caso.resposta_ao_cliente = texto
    agente.executar(caso, agente._proposta(caso, "responder_cliente", motivo=texto))
    _atualizar_estado(agente, caso)
    return caso


def rejeitar(agente: Agente, aprovacao_id: str, supervisor_id: str, justificativa: str) -> Caso:
    aprovacao = _pendente(agente, aprovacao_id, supervisor_id)
    if not justificativa.strip():
        raise AprovacaoRecusada("Rejeição exige justificativa.")
    caso = agente.casos[aprovacao.acao.conversation_id]
    agente.executar(
        caso, _ato_do_supervisor("rejeitar_acao", aprovacao, supervisor_id, justificativa)
    )
    aprovacao.estado, aprovacao.decidido_por, aprovacao.comentario = (
        "rejeitada",
        supervisor_id,
        justificativa,
    )
    _fechar_no_canal(agente, aprovacao)
    agente.postar_no_canal(
        "aviso",
        supervisor_id,
        f"{caso.conversation_id}: {nome_da_acao(aprovacao.acao.ferramenta)} rejeitado por "
        f"{supervisor_id}. "
        f"Justificativa: {justificativa}",
        caso.conversation_id,
        aprovacao_id=aprovacao_id,
    )
    texto = (
        "Analisamos sua solicitação e uma pessoa da nossa equipe vai falar com você "
        "por aqui sobre os próximos passos."
    )
    caso.resposta_ao_cliente = texto
    agente.executar(caso, agente._proposta(caso, "responder_cliente", motivo=texto))
    _atualizar_estado(agente, caso)
    return caso
