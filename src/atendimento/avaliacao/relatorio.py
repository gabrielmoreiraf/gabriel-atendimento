"""Relatório Markdown da avaliação offline (HG-18), com a consulta de origem de cada número."""

from __future__ import annotations

from collections import Counter

from atendimento.avaliacao.categoria import (
    acerto_categoria,
    escalacoes_corretas,
    piores_categorias,
)
from atendimento.avaliacao.historico import Historico
from atendimento.avaliacao.offline import (
    FERRAMENTAS_COM_DINHEIRO,
    LinhaAcao,
    avaliar_acoes,
    avaliar_anexos,
    casos_m11,
)
from atendimento.contratos import Resultado
from atendimento.politicas.motor import LIMITE_POR_FERRAMENTA
from atendimento.verificacao import FATOR_CUSTO_ACEITAR_FALSO

DIVERGENCIAS = {
    "alcada_acumulada": "Cada ação cabe na alçada, mas a soma no pedido passa do limite (Q10, HG-22)",
    "alcada": "A ação sozinha passa do limite e não teve aprovação (EC-01, EC-02, HG-05)",
    "prazo": "Fora dos dias corridos do recebimento da categoria (EC-03)",
    "antes_do_recebimento": "Ação antes da entrega (ou sem entrega) em categoria com prazo do "
    "recebimento: o agente escala para conferir com a logística (EC-25, Q12)",
    "troca_repetida": "Segunda troca no mesmo pedido (HG-22)",
    "acao_nao_permitida": "Ferramenta fora de `categorias.<categoria>.acoes_permitidas` para a "
    "tag da conversa: o agente escala",
    "sem_pedido": "Ação com dinheiro sem pedido identificado: o agente escala (Q20)",
    "caso_sensivel": "Caso sensível: o agente escalaria (HG-06)",
    "autoaprovacao": "Quem executou é quem aprovou (HG-03)",
    "outro": "Outro motivo",
}


def _rs(valor: float) -> str:
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def _pct(parte: int, total: int) -> str:
    return f"{100 * parte / total:.1f}%".replace(".", ",") if total else "0,0%"


def _tabela(cabecalho: list[str], linhas: list[list[object]]) -> str:
    saida = ["| " + " | ".join(cabecalho) + " |", "|" + "---|" * len(cabecalho)]
    saida += ["| " + " | ".join(str(c) for c in linha) + " |" for linha in linhas]
    return "\n".join(saida)


def _secao_acoes(linhas: list[LinhaAcao], historico: Historico) -> str:
    total = len(linhas)
    divergentes = [x for x in linhas if x.divergencia]
    resultados = [r.value for r in Resultado]

    por_acao = []
    for acao in FERRAMENTAS_COM_DINHEIRO:
        da_acao = [x for x in linhas if x.acao == acao]
        cont = Counter(x.decisao.resultado.value for x in da_acao)
        por_acao.append(
            [acao, len(da_acao), sum(1 for x in da_acao if x.aprovado_por)]
            + [cont.get(r, 0) for r in resultados]
            + [sum(1 for x in da_acao if x.divergencia)]
        )
    cont_total = Counter(x.decisao.resultado.value for x in linhas)
    por_acao.append(
        ["**total**", total, sum(1 for x in linhas if x.aprovado_por)]
        + [cont_total.get(r, 0) for r in resultados]
        + [len(divergentes)]
    )

    cont_div = Counter(x.divergencia for x in divergentes)
    tabela_div = [
        [
            f"`{chave}`",
            texto,
            cont_div[chave],
            _rs(sum(x.valor_rs for x in divergentes if x.divergencia == chave)),
        ]
        for chave, texto in DIVERGENCIAS.items()
        if cont_div.get(chave)
    ]

    fora = Counter(
        (x.categoria, x.acao) for x in divergentes if x.divergencia == "acao_nao_permitida"
    )
    tabela_fora = [[f"`{c}`", a, n] for (c, a), n in fora.most_common()] or [["-", "-", 0]]

    casos = casos_m11(historico.acoes, historico.politicas)
    pegos = {(x.order_id, x.acao) for x in divergentes}
    linhas_m11 = []
    for order_id, acao in casos:
        do_caso = [x for x in linhas if x.order_id == order_id and x.acao == acao]
        primeira_barrada = next((x for x in do_caso if x.divergencia), None)
        linhas_m11.append(
            [
                order_id,
                acao,
                len({x.conversation_id for x in do_caso}),
                _rs(sum(x.valor_rs for x in do_caso)),
                _rs(float(historico.politicas[LIMITE_POR_FERRAMENTA[acao]])),
                primeira_barrada.acao_id if primeira_barrada else "não barrada",
                primeira_barrada.decisao.resultado.value if primeira_barrada else "-",
            ]
        )
    pegos_m11 = sum(1 for c in casos if c in pegos)
    barradas = Counter(linha[-1] for linha in linhas_m11 if linha[-1] != "-")
    como = ", ".join(f"`{r}` em {n}" for r, n in barradas.most_common())

    return f"""## 1. Ações com dinheiro: o que o agente teria decidido

**{total}** ações com dinheiro no histórico. O agente teria decidido diferente do time em
**{len(divergentes)}** ({_pct(len(divergentes), total)}). Essas ações somam
**{_rs(sum(x.valor_rs for x in divergentes))}** que o agente não teria executado sozinho.

{_tabela(["ação", "ações", "com aprovação no histórico", *resultados, "divergem"], por_acao)}

### Por que divergem

{_tabela(["motivo", "descrição", "ações", "valor executado"], tabela_div)}

### Ações fora das permitidas, por categoria

A categoria vem da `tag_agente` humana, e parte pode ser tag imprecisa: conversas marcadas
"Rastreio" com reenvio ou reembolso, ações que a política só prevê em `atraso_entrega`. O agente
classifica a conversa de novo antes de decidir, então este número é teto, não previsão.

{_tabela(["categoria (pela tag)", "ação executada", "ações"], tabela_fora)}

### M11: soma acima da alçada sem aprovação (Q10)

**{len(casos)}** pares (pedido, ação) em que a mesma ação se repetiu em conversas diferentes,
cada execução dentro da alçada, nenhuma aprovada, e a soma passou do limite. O motor barra
**{pegos_m11} de {len(casos)}** antes de o dinheiro sair. Primeira ação barrada em cada caso: {como}
(`negar` quando a mesma ação também cai fora do prazo ou é a segunda troca; `escalar` quando
veio antes da entrega registrada ou fora das ações permitidas da categoria).

{_tabela(["pedido", "ação", "conversas", "soma executada", "limite", "1ª ação barrada", "decisão do agente"], linhas_m11)}
"""


def _secao_anexos(historico: Historico) -> str:
    linhas = avaliar_anexos(
        historico.anexos,
        pedidos=historico.pedidos,
        conversas=historico.conversas,
        acoes=historico.acoes,
        trocas_reenvios=historico.trocas_reenvios,
        enviado_em=historico.anexo_enviado_em,
    )
    suspeitas = [x for x in linhas if x.veredicto.suspeita]
    pagas = [x for x in suspeitas if x.acoes_com_dinheiro]
    custo = round(sum(x.custo_evitado_rs for x in pagas), 2)
    cont_acao = Counter(a for x in pagas for a in set(x.acoes_com_dinheiro))
    cont_sinal = Counter(
        s.tipo.value for x in suspeitas for s in {s.tipo: s for s in x.veredicto.sinais}.values()
    )
    tabela_casos = [
        [
            x.conversation_id,
            x.order_id,
            ", ".join(sorted({s.tipo.value for s in x.veredicto.sinais})),
            ", ".join(sorted(set(x.acoes_com_dinheiro))),
            _rs(historico.pedidos[x.order_id].valor),
            _rs(x.custo_evitado_rs),
        ]
        for x in pagas
    ]
    return f"""## 2. Reclamações com anexo suspeito que receberam dinheiro

**{len(linhas)}** conversas com anexo e pedido identificado. O verificador marca
**{len(suspeitas)}** como suspeitas. Dessas, **{len(pagas)}** receberam reenvio, reimpressão,
troca ou reembolso no histórico. Com o agente, iriam para o supervisor (`sinalizar_suspeita`)
antes de qualquer gasto.

**Custo evitado estimado: {_rs(custo)}** (soma de valor do pedido × {str(FATOR_CUSTO_ACEITAR_FALSO).replace(".", ",")}
nas {len(pagas)} conversas, `parametros.md`: custo de reenviar/reembolsar uma reclamação que
não procede). É um valor esperado: suspeita não é fraude confirmada, e o supervisor pode aprovar.

{_tabela(["ação recebida", "conversas suspeitas"], [[a, n] for a, n in cont_acao.most_common()])}

{_tabela(["sinal", "conversas suspeitas com o sinal"], [[s, n] for s, n in cont_sinal.most_common()])}

{_tabela(["conversa", "pedido", "sinais", "ações com dinheiro", "valor do pedido", "custo evitado"], tabela_casos)}
"""


def _secao_categoria(historico: Historico) -> str:
    linhas = acerto_categoria(
        historico.conversas, historico.mensagens_do_cliente, historico.politicas
    )
    avaliadas = [x for x in linhas if x.acertou is not None]
    acertos = sum(1 for x in avaliadas if x.acertou)
    sem = len(linhas) - len(avaliadas)
    tabela = []
    for tag, n in Counter(x.tag_agente for x in avaliadas).most_common():
        da_tag = [x for x in avaliadas if x.tag_agente == tag]
        certos = sum(1 for x in da_tag if x.acertou)
        confusoes = Counter(x.tag_prevista for x in da_tag if not x.acertou).most_common(2)
        tabela.append(
            [
                tag,
                n,
                certos,
                _pct(certos, n),
                ", ".join(f"{t} ({q})" for t, q in confusoes) or "-",
            ]
        )
    piores = piores_categorias(linhas, quantas=3)
    texto_piores = "; ".join(f"{t} ({_pct(c, n)} de {n})" for t, n, c, _ in piores)
    sensiveis = {x.conversation_id for x in avaliadas if x.categoria == "reacao_adversa"}
    esc = escalacoes_corretas(sensiveis, historico.acoes)
    return f"""## 3. Categoria: o leitor do agente contra a tag humana

O leitor (`atendimento.agente.leitor.ler`) leu as mensagens do cliente de
**{len(linhas)}** conversas. **{sem}** não têm mensagem do cliente (só o bot falou) e ficam
fora da conta. Nas **{len(avaliadas)}** restantes, a categoria do leitor bate com a
`tag_agente` em **{acertos}** ({_pct(acertos, len(avaliadas))}).

{
        _tabela(
            ["tag humana", "conversas", "acertos", "acerto", "o leitor disse (erros mais comuns)"],
            tabela,
        )
    }

As três tags com menor acerto são {texto_piores}. É por elas que o classificador
melhora primeiro.

### Escalações corretas (casos sensíveis)

Critério: o leitor marca a conversa como sensível quando a categoria é `reacao_adversa`
(o agente escala para a supervisão, HG-06). No histórico, conta como **escalação humana** a
conversa com `registrar_cosmetovigilancia` (só supervisor) ou com alguma ação com
`aprovado_por` em `acoes_executadas_sistemas.csv`; o histórico não registra `acionar_pessoa`.

{
        _tabela(
            ["medida", "conversas"],
            [
                ["sensíveis pelo leitor (reação adversa)", esc["sensiveis_leitor"]],
                [
                    "dessas, com escalação humana no histórico",
                    f"{esc['com_escalacao_humana']} ({_pct(esc['com_escalacao_humana'], esc['sensiveis_leitor'])})",
                ],
                [
                    "conversas com cosmetovigilância registrada pelo time",
                    esc["cosmetovigilancia_humana"],
                ],
                [
                    "dessas, marcadas como sensíveis pelo leitor",
                    f"{esc['cosmetovigilancia_vista_pelo_leitor']} ({_pct(esc['cosmetovigilancia_vista_pelo_leitor'], esc['cosmetovigilancia_humana'])})",
                ],
            ],
        )
    }
"""


CONSULTAS = """## Consultas de origem

Tudo sai de `python -m atendimento.avaliacao` (lê `docs/` com o módulo `csv`, UTF-8,
separador `,`, somente leitura). Código: `src/atendimento/avaliacao/`.

| número | consulta |
|---|---|
| ações com dinheiro | `acoes_executadas_sistemas.csv`: linhas com `acao` em reembolsar, reenviar_produto, reimprimir_personalizacao, trocar_produto e `valor_rs` preenchido, em ordem de `data_hora`, `acao_id` |
| decisão do agente | `atendimento.politicas.decidir` para cada linha, com "agora" = `data_hora` da ação; `acoes_anteriores` = linhas anteriores do mesmo `order_id`; `aprovado_por` do histórico vira aprovação; papel por `equipe_atendimento.cargo` de `executado_por`; categoria por `historico_conversas.tag_agente` → `politicas.csv` `categorias.*.tag_equivalente`; pedido de `pedidos.csv` (`data_separacao`, `data_entrega`) |
| divergência | decisão do agente ≠ `executar` (o time executou todas as ações); motivo pela `regra` da decisão |
| limites | `politicas.csv`: `limites_por_papel.atendente.reembolso_max_rs`, `reenvio_ou_reimpressao_max_rs`, `troca_max_rs` |
| M11 | `acoes_executadas_sistemas.csv` agrupado por (`order_id`, `acao`): 2+ `conversation_id` distintos, `aprovado_por` vazio em todas, cada `valor_rs` ≤ limite, soma > limite (mesma regra de `ingestao/baseline_metricas.md`, M11) |
| conversas com anexo | `anexos_conversas.csv` agrupado por `conversation_id`; pedido por `historico_conversas.order_id` (ou `anexos_conversas.order_id`) em `pedidos.csv` + `itens_pedido.csv` |
| suspeita | `atendimento.verificacao.verificar`, com anexos do mesmo `hash_perceptual` enviados antes (`enviado_em`) e reenvios do cliente em `trocas_reenvios.csv` (`tipo` = reenvio, EC-19) com `data_solicitacao` < `historico_conversas.data_abertura` |
| receberam dinheiro | conversa suspeita com ao menos uma ação com dinheiro em `acoes_executadas_sistemas.csv` (mesmo `conversation_id`) |
| acerto de categoria | `historico_mensagens.csv` com `autor` = cliente, por `conversation_id` em ordem de `timestamp`; `atendimento.agente.leitor.ler` no texto; categoria → `politicas.csv` `categorias.*.tag_equivalente` (rastreio → onde_esta_pedido, atraso → atraso_entrega, arrependimento → arrependimento_cancelamento; sem tag_equivalente → "Reclamação produto"; outros → "Outros"); comparação com `historico_conversas.tag_agente` |
| custo evitado | soma de `VeredictoEvidencia.custo_aceitar_falso_rs` = `pedidos.valor` × 0,45 (`parametros.md`) nessas conversas |
"""

PREMISSAS = """## Premissas e limites

- O histórico é reexecutado como aconteceu: a soma por pedido usa as ações que o time de fato
  executou antes, mesmo as que o agente teria segurado.
- A categoria vem da `tag_agente` humana. "Reclamação produto" e "Outros" não têm categoria em
  `politicas.csv`; nelas o motor aplica só a alçada (sem prazo, sem caso sensível).
- Ações aprovadas no histórico contam como aprovação válida (o aprovador é supervisor), mas
  entram na soma da alçada do pedido (Q10): uma aprovação cobre só a ação aprovada.
- "Financeiro" junta cobrança duplicada e pagamento pendente; o leitor só tem a primeira.
- Escalações corretas medem só casos sensíveis (reação adversa); escalações por alçada estão
  na seção 1.
"""


def gerar_relatorio(historico: Historico) -> str:
    linhas = avaliar_acoes(
        historico.acoes,
        pedidos=historico.pedidos,
        conversas=historico.conversas,
        politicas=historico.politicas,
        equipe=historico.equipe,
    )
    return "\n".join(
        [
            "# Avaliação offline contra o histórico (HG-18)",
            "",
            "Reexecução do motor de políticas (`atendimento.politicas`) e do verificador de "
            "evidência (`atendimento.verificacao`) sobre o histórico de `docs/`. Gerado por "
            "`uv run python -m atendimento.avaliacao`; não edite à mão.",
            "",
            _secao_acoes(linhas, historico),
            _secao_anexos(historico),
            _secao_categoria(historico),
            CONSULTAS,
            PREMISSAS,
        ]
    )
