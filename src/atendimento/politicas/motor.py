"""Motor de políticas: decide se o agente executa, pede aprovação, nega, escala ou bloqueia.

Código puro, sem I/O. Recebe as dataclasses de `contratos.py` e o dict de políticas
(`secao.regra -> valor`, como em `docs/politicas.csv`). Toda `Decisao` cita em `regra`
a chave de `politicas.csv` que a fundamenta.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from atendimento.contratos import (
    AGORA,
    FUSO,
    AcaoAnterior,
    AcaoProposta,
    Decisao,
    Papel,
    Pedido,
    Resultado,
    VeredictoEvidencia,
)

# Famílias de limite (Q10): reembolsos somam entre si; reenvio, reimpressão e troca somam juntos.
LIMITE_POR_FERRAMENTA = {
    "reembolsar": "limites_por_papel.atendente.reembolso_max_rs",
    "reenviar_produto": "limites_por_papel.atendente.reenvio_ou_reimpressao_max_rs",
    "reimprimir_personalizacao": "limites_por_papel.atendente.reenvio_ou_reimpressao_max_rs",
    "trocar_produto": "limites_por_papel.atendente.troca_max_rs",
}
GRUPO_DE_LIMITE = {
    "reembolsar": "reembolso",
    "reenviar_produto": "reposicao",
    "reimprimir_personalizacao": "reposicao",
    "trocar_produto": "reposicao",
}
SO_ANTES_DA_SEPARACAO = {
    "cancelar_pedido": "categorias.arrependimento_cancelamento.regra",
    "alterar_endereco": "categorias.alteracao_endereco.regra",
}
# Ferramentas com efeito que precisam estar em categorias.<cat>.acoes_permitidas.
COM_EFEITO = frozenset(LIMITE_POR_FERRAMENTA) | frozenset(SO_ANTES_DA_SEPARACAO)
# Nome curto usado pela classificação -> categoria de politicas.csv.
ALIAS_CATEGORIA = {"avaria": "avaria_vazamento", "arrependimento": "arrependimento_cancelamento"}

REGRA_AUTOAPROVACAO = "limites_por_papel.supervisor.nao_aprova_a_propria_acao"
REGRA_QUEM_DECIDE = "reclamacao_suspeita.quem_decide"
REGRA_SINALIZAR = "reclamacao_suspeita.atendente_e_analista"
REGRA_MAX_TROCAS = "categorias.troca_fragrancia.max_trocas_por_pedido"
REGRA_REACAO = "categorias.reacao_adversa.acoes_obrigatorias"

_TURNO = re.compile(r"(\d{1,2})h\s*-\s*(\d{1,2})h")


def dentro_da_janela(data_entrega: date | datetime | None, agora=AGORA, dias: int = 7) -> bool:
    """EC-03: dias corridos desde o recebimento; o último dia está dentro. Sem entrega, fora."""
    if data_entrega is None:
        return False
    if isinstance(data_entrega, datetime):
        data_entrega = (
            data_entrega.astimezone(FUSO).date() if data_entrega.tzinfo else data_entrega.date()
        )
    corridos = (_local(agora).date() - data_entrega).days
    return 0 <= corridos <= dias


def supervisor_no_turno(
    equipe: list[dict],
    agora=AGORA,
    *,
    preferido: str | None = None,
    excluir: str | None = None,
) -> str | None:
    """EC-22: supervisor ativo cujo turno cobre `agora`; `preferido` ganha se estiver no turno.

    `excluir` é quem propôs a ação (não aprova a própria). Sem ninguém no turno, devolve None.
    """
    hora = _local(agora)
    minutos = hora.hour * 60 + hora.minute
    disponiveis = []
    for pessoa in equipe:
        if pessoa.get("cargo") != Papel.SUPERVISOR or pessoa.get("status", "ativo") != "ativo":
            continue
        if pessoa["colaborador_id"] == excluir:
            continue
        faixa = _TURNO.search(pessoa.get("turno", ""))
        if faixa and int(faixa[1]) * 60 <= minutos < int(faixa[2]) * 60:
            disponiveis.append(pessoa["colaborador_id"])
    if preferido in disponiveis:
        return preferido
    return min(disponiveis) if disponiveis else None


def decidir(
    acao: AcaoProposta,
    *,
    pedido: Pedido | None,
    acoes_anteriores: list[AcaoAnterior],
    politicas: dict[str, str],
    equipe: list[dict],
    agora=AGORA,
    veredicto: VeredictoEvidencia | None = None,
    sinalizado_por: str | None = None,
    supervisor_preferido: str | None = None,
) -> Decisao:
    categoria = ALIAS_CATEGORIA.get(acao.categoria or "", acao.categoria)

    def aprovador() -> str | None:
        return supervisor_no_turno(
            equipe, agora, preferido=supervisor_preferido, excluir=acao.executado_por
        )

    # HG-03: ninguém aprova a própria ação.
    if acao.aprovado_por and acao.aprovado_por == acao.executado_por:
        return Decisao(
            Resultado.BLOQUEAR,
            REGRA_AUTOAPROVACAO,
            "Quem executa a ação não pode ser quem a aprova; a aprovação vai para outro supervisor.",
            aprovador_sugerido=aprovador(),
        )

    # HG-04: quem sinalizou a suspeita não decide nem aprova; só supervisor decide.
    if acao.ferramenta == "decidir_suspeita":
        if acao.papel is not Papel.SUPERVISOR:
            return Decisao(
                Resultado.BLOQUEAR,
                REGRA_QUEM_DECIDE,
                f"Só o papel '{politicas.get(REGRA_QUEM_DECIDE, 'supervisor')}' decide suspeita.",
            )
        if sinalizado_por and acao.executado_por == sinalizado_por:
            return Decisao(
                Resultado.BLOQUEAR, REGRA_QUEM_DECIDE, "Quem sinalizou a suspeita não a decide."
            )
        return Decisao(Resultado.EXECUTAR, REGRA_QUEM_DECIDE, "Supervisor decide a suspeita.")
    if sinalizado_por and acao.aprovado_por == sinalizado_por:
        return Decisao(
            Resultado.BLOQUEAR,
            REGRA_QUEM_DECIDE,
            "Quem sinalizou a suspeita não aprova a ação do mesmo caso.",
        )

    # HG-06: reação adversa sempre vai para a supervisão, com ações obrigatórias.
    if categoria == "reacao_adversa":
        obrigatorias = _lista(politicas.get(REGRA_REACAO, ""))
        prazo = politicas.get("categorias.reacao_adversa.prazo_registro_horas")
        return Decisao(
            Resultado.ESCALAR,
            REGRA_REACAO,
            "Reação adversa: orientar a suspensão do uso e o supervisor registra a "
            "cosmetovigilância. Trocar o produto não substitui o registro.",
            aprovador_sugerido=aprovador(),
            acoes_obrigatorias=obrigatorias,
            detalhes={"prazo_registro_horas": int(prazo) if prazo else None},
        )

    # Ação com efeito fora das ações permitidas da categoria: uma pessoa decide.
    chave_permitidas = f"categorias.{categoria}.acoes_permitidas"
    if (
        acao.ferramenta in COM_EFEITO
        and categoria
        and chave_permitidas in politicas
        and acao.ferramenta not in _lista(politicas[chave_permitidas])
    ):
        return Decisao(
            Resultado.ESCALAR,
            chave_permitidas,
            f"'{acao.ferramenta}' não está entre as ações permitidas para {categoria}.",
            aprovador_sugerido=aprovador(),
        )

    # Cancelamento e troca de endereço só antes da separação.
    if acao.ferramenta in SO_ANTES_DA_SEPARACAO:
        regra = SO_ANTES_DA_SEPARACAO[acao.ferramenta]
        if pedido is None:
            return Decisao(
                Resultado.ESCALAR, regra, "Pedido não encontrado: não dá para conferir a separação."
            )
        if pedido.data_separacao is None:
            return Decisao(Resultado.EXECUTAR, regra, "Pedido ainda não separado.")
        return Decisao(
            Resultado.NEGAR,
            regra,
            f"Pedido separado em {pedido.data_separacao.isoformat()}: {politicas.get(regra, '')}".strip(),
        )

    chave_limite = LIMITE_POR_FERRAMENTA.get(acao.ferramenta)
    if chave_limite is None:
        regra = f"categorias.{categoria}.acoes_permitidas" if categoria else "dominio.dominio"
        return Decisao(
            Resultado.EXECUTAR, regra, "Ação sem valor em dinheiro nem prazo a conferir."
        )

    # Q20: ação com dinheiro sem pedido identificado nunca executa.
    if pedido is None:
        return Decisao(
            Resultado.ESCALAR,
            chave_limite,
            "Pedido não identificado: ação com dinheiro exige conferir pedido e item antes.",
            aprovador_sugerido=aprovador(),
        )

    anteriores = [a for a in acoes_anteriores if a.order_id == acao.order_id]

    # HG-22: 1 troca por pedido.
    if acao.ferramenta == "trocar_produto":
        max_trocas = int(politicas.get(REGRA_MAX_TROCAS, "1"))
        trocas = sum(1 for a in anteriores if a.acao == "trocar_produto")
        if trocas >= max_trocas:
            return Decisao(
                Resultado.NEGAR,
                REGRA_MAX_TROCAS,
                f"O pedido já teve {trocas} troca(s); a política permite {max_trocas} por pedido.",
            )

    # EC-03: prazo em dias corridos do recebimento, quando a categoria tem prazo.
    chave_prazo = f"categorias.{categoria}.prazo_dias_corridos_do_recebimento"
    if categoria and chave_prazo in politicas:
        dias = int(politicas[chave_prazo])
        entrega = pedido.data_entrega if pedido else None
        # EC-25 / Q12: sem entrega registrada (ou com data futura) a janela nem começou;
        # não há prazo vencido para negar, então uma pessoa confere com a logística.
        if entrega is None or entrega > _local(agora).date():
            return Decisao(
                Resultado.ESCALAR,
                chave_prazo,
                "pedido sem entrega registrada; conferir com logística",
                aprovador_sugerido=aprovador(),
            )
        if not dentro_da_janela(entrega, agora, dias):
            return Decisao(
                Resultado.NEGAR,
                chave_prazo,
                f"Fora do prazo de {dias} dias corridos do recebimento ({entrega.isoformat()}). "
                f"{politicas.get(f'categorias.{categoria}.regra', '')}".strip(),
            )

    # HG-08: suspeita nunca vira negação do atendente; vai para o supervisor.
    if veredicto is not None and veredicto.suspeita and acao.papel is not Papel.SUPERVISOR:
        return Decisao(
            Resultado.SINALIZAR_SUSPEITA,
            REGRA_SINALIZAR,
            "Evidência incoerente com o pedido: o supervisor decide; o cliente é informado "
            "apenas de que a solicitação está em análise.",
            aprovador_sugerido=aprovador(),
            detalhes={"sinais": [s.tipo.value for s in veredicto.sinais]},
        )

    # EC-01, EC-02, HG-22 (Q10): alçada acumulada por pedido e por família de limite.
    # Soma TODAS as ações anteriores do grupo, aprovadas ou não: a aprovação cobre só a
    # ação aprovada (SPEC.md, Q10). Quem valida o aprovacao_id é o agente (Q21).
    limite = float(politicas[chave_limite])
    grupo = GRUPO_DE_LIMITE[acao.ferramenta]
    acumulado = round(
        sum(a.valor_rs for a in anteriores if GRUPO_DE_LIMITE.get(a.acao) == grupo),
        2,
    )
    total = round(acumulado + acao.valor_rs, 2)
    detalhes = {"limite_rs": limite, "acumulado_rs": acumulado, "total_rs": total}
    # EC-03 / Q18: reembolso por arrependimento depois do recebimento leva coleta reversa,
    # que não tem ferramenta própria (sai por acionar_pessoa para a logística).
    obrigatorias: tuple[str, ...] = ()
    if categoria == "arrependimento_cancelamento" and acao.ferramenta == "reembolsar":
        obrigatorias = ("coleta_reversa",)
        detalhes["coleta_reversa"] = True
    if total <= limite:
        return Decisao(
            Resultado.EXECUTAR,
            chave_limite,
            f"R$ {total:.2f} no pedido, dentro do limite de R$ {limite:.2f}.",
            acoes_obrigatorias=obrigatorias,
            detalhes=detalhes,
        )
    if acao.aprovacao_id and _e_supervisor(acao.aprovado_por, equipe):
        return Decisao(
            Resultado.EXECUTAR,
            chave_limite,
            f"Acima do limite de R$ {limite:.2f}, com aprovação {acao.aprovacao_id} "
            f"de {acao.aprovado_por}.",
            acoes_obrigatorias=obrigatorias,
            detalhes=detalhes,
        )
    quem = aprovador()
    if quem is None:
        detalhes["fila_ate"] = politicas.get("horario_atendimento_humano.inicio", "08:00")
    return Decisao(
        Resultado.PEDIR_APROVACAO,
        chave_limite,
        f"R$ {total:.2f} no pedido (R$ {acumulado:.2f} já executados antes) passa do "
        f"limite de R$ {limite:.2f}: solicitar_aprovacao ao supervisor.",
        aprovador_sugerido=quem,
        detalhes=detalhes,
    )


def _local(agora: datetime) -> datetime:
    return agora.astimezone(FUSO) if agora.tzinfo else agora


def _lista(valor: str) -> tuple[str, ...]:
    return tuple(p.strip() for p in valor.split(";") if p.strip())


def _e_supervisor(colaborador_id: str | None, equipe: list[dict]) -> bool:
    return bool(colaborador_id) and any(
        p["colaborador_id"] == colaborador_id
        and p.get("cargo") == Papel.SUPERVISOR
        and p.get("status", "ativo") == "ativo"
        for p in equipe
    )
