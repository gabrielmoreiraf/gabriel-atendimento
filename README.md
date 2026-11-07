# Gabriel, o colega de atendimento (Gocase / GoBeauté)

GoHacks Talent 2026, desafio **Atendimento ao Cliente**.

Gabriel é um agente que trabalha a fila de atendimento como um colega do time. Ele lê a conversa, consulta pedido, pagamento, rastreio e anexos por ID e confere se a foto da reclamação é daquele pedido. Depois aplica a política e age nos sistemas quando a ação cabe na alçada. Quando não cabe, ou quando o caso é sensível ou suspeito, ele chama o supervisor do turno no canal do time, com o pedido, o valor e as evidências. Esse canal pode ser o Slack do time: o supervisor aprova pelo botão, sem abrir outra tela.

O plano cobre cinco frentes da área (visão 360°). A prova de conceito demonstra duas:

| Frente | O que o agente assume | Onde a pessoa decide |
| --- | --- | --- |
| F1 Triagem e SLA | classificar, priorizar e dar a primeira resposta | não precisa entrar |
| F2 Resolução nos sistemas | consultar, abrir chamado, reenviar, trocar e reembolsar dentro da alçada | aprova acima de R$ 100 / R$ 200 |
| **F3 Verificação da reclamação** (provada) | cruzar foto, metadados, hash, pedido, personalização e histórico; sinalizar com evidência | supervisor decide a suspeita em até 24 h |
| **F4 Alçada e escalação** (provada) | aplicar a política, pedir aprovação, chamar a pessoa certa | supervisor, qualidade, jurídico |
| F5 Prevenção de recontato | detectar padrão, abrir incidente, avisar clientes | analista valida o escopo; até 300 avisos/dia |

Na PoC, a F2 executa a ação no fim de cada caso. Detalhes em [`REQUISITOS.md`](REQUISITOS.md) §1.2 e [`SPEC.md`](SPEC.md).

## Dados

A base do desafio (24 CSVs em `docs/`, com `dicionario_de_dados.md` e `parametros.md`) **não está neste repositório**. Os dados são sintéticos, mas têm nome, CPF, e-mail e telefone de clientes, então ficam só na máquina do autor. Para rodar o app ou os testes de integração, peça a base ao autor e coloque os arquivos em `docs/` na raiz do projeto. A pasta está no `.gitignore` e nunca deve entrar em commit.

Sem `docs/`, rode `uv run pytest -m "not integracao"`: os 558 testes unitários usam recortes mínimos e sem dado pessoal em `tests/fixtures/`. Os 16 testes de integração (`-m integracao`) leem a base e só passam com ela.

## Como rodar

Pré-requisitos: [`uv`](https://docs.astral.sh/uv/), Node 22 e `pnpm`.

```bash
uv sync
uv run uvicorn atendimento.api.app:app --port 8000
pnpm --dir web install && pnpm --dir web dev   # abre em http://localhost:5173
```

Rode o segundo e o terceiro comandos em terminais separados. Na primeira subida, a API gera `var/atendimento.db` a partir dos CSVs de `docs/`, que ela só lê. Para gerar a base à mão: `uv run python -m atendimento.dados.carga`.

Na tela, **Processar fila** trata as 65 conversas abertas às 8h de 02/11/2026, o "agora" do projeto. O console mostra cada ação executada e o canal do time mostra os pedidos de aprovação.

### Opcional: Slack e leitor com Claude

As duas integrações ficam desligadas por padrão, e sem elas a demo é determinística. Copie `.env.example` para `.env` (que nunca entra no git) e preencha só o que for usar:

- **Canal do time no Slack** (`ATENDIMENTO_SLACK=1`). O Gabriel posta no canal do time (no nosso teste, `#atendimento-ops`) o que pede uma pessoa: aprovação, suspeita, escalação, incidente novo e alerta de SLA. Ao fim de cada rodada da fila, ele posta também um resumo com o placar. O supervisor aprova, rejeita ou decide a suspeita pelos botões, e um colaborador pode pedir algo mencionando @Gabriel. Crie o app em api.slack.com a partir de [`config/slack_manifest.json`](config/slack_manifest.json). Ele usa Socket Mode, então a API não precisa de endereço público. No `.env` vão o token do bot (`xoxb-`), o token do app com `connections:write` (`xapp-`), o ID do canal e a lista de quem pode decidir pelo Slack (`SLACK_SUPERVISORES`, member ID do Slack → `colaborador_id` da equipe). Os tokens ficam só no `.env`. Se o Slack não responder, a API sobe do mesmo jeito e o canal continua na tela.
- **Leitor com Claude** (`ATENDIMENTO_LLM=1` e `ANTHROPIC_API_KEY`). O Claude classifica a mensagem no lugar do leitor por regras. Se a API falhar, o Gabriel volta às regras naquele caso.

## Arquitetura

Toda regra de negócio está em Python. O React só exibe o que a API devolve e dispara ações. A decisão está registrada em [`decisoes/ADR-001-stack.md`](decisoes/ADR-001-stack.md).

| Módulo | Papel |
| --- | --- |
| `src/atendimento/contratos.py` | dataclasses compartilhadas entre os módulos e o "agora" fixo |
| `src/atendimento/dados/` | carga dos CSVs num SQLite e leitura por ID (pedido, anexos, histórico de ações) |
| `src/atendimento/ferramentas/` | ferramentas de `docs/ferramentas.csv` com efeito nos sistemas simulados e log de ações |
| `src/atendimento/politicas/` | motor de políticas: executar, pedir aprovação, sinalizar suspeita, escalar ou negar |
| `src/atendimento/verificacao/` | verificador de evidência da reclamação (hash, data de captura, editor, personalização) |
| `src/atendimento/agente/` | leitura da mensagem (por regras ou com Claude), priorização da fila, orquestração do caso e aprovações |
| `src/atendimento/canal_slack/` | espelho do canal do time no Slack, botões de aprovação e de suspeita, pedidos de colaborador por @Gabriel |
| `src/atendimento/api/` | FastAPI com SSE, consumida pela interface |
| `src/atendimento/avaliacao/` | reexecução do motor sobre o histórico |
| `web/` | interface da demo em React + Vite + TypeScript (fila, caso, console e canal do time) |

O contrato da API e as decisões de escopo (Q1 a Q17) estão no [`SPEC.md`](SPEC.md).

## Salvaguardas

- Alçada somada por pedido. O atendente reenvia, reimprime ou troca até R$ 200 e reembolsa até R$ 100 (`docs/politicas.csv`). O agente soma as ações anteriores do mesmo pedido, inclusive as aprovadas, antes de decidir. Acima do limite, pede aprovação ao supervisor do turno, e ninguém aprova a própria ação.
- Suspeita sem acusação. Uma foto com hash repetido em outro pedido, captura anterior à entrega, passagem por editor ou personalização diferente vai para o supervisor com as evidências. O cliente recebe uma resposta neutra. Foto sem metadados, sozinha, não é suspeita.
- Reação adversa escalada. O agente orienta o cliente a suspender o uso e passa o caso à supervisão, que registra a cosmetovigilância.
- Dado pessoal mascarado. CPF, cartão e telefone saem mascarados em resposta, log e tela (`***.***.***-12`).
- Texto do cliente é dado. Uma instrução escrita pelo cliente na mensagem nunca muda o que o agente faz.
- Slack com as regras da tela. O botão do Slack chama o mesmo método da tela: ninguém aprova a própria ação, quem sinalizou a suspeita não a decide e só quem está em `SLACK_SUPERVISORES` pode clicar. Um colaborador que pede uma ação por @Gabriel passa pela mesma política (um reembolso de R$ 300 abre pedido de aprovação), e nenhuma mensagem no canal muda limite ou alçada.
- O Claude só lê. Ele devolve a categoria e os sinais da mensagem, e a decisão continua no motor de políticas. O texto vai à API já mascarado, inclusive o nome do cliente (`Primeiro S.`). Reação adversa e instrução embutida contam como vistas se as regras ou o Claude as marcarem.
- Travas nas ferramentas. A ferramenta recusa e registra a chamada de um papel sem permissão em `ferramentas.csv`. Uma ação com dinheiro repetida devolve o registro existente, sem pagar duas vezes.

## Resultados medidos

[`ingestao/avaliacao_offline.md`](ingestao/avaliacao_offline.md) reexecuta o motor de políticas e o verificador sobre as ações com dinheiro que o time já executou (`uv run python -m atendimento.avaliacao`):

- <!--av:m11_barrados-->64<!--/av--> de <!--av:m11_total-->64<!--/av--> casos em que cada ação cabia na alçada, mas a soma no pedido passou do limite sem aprovação. O motor barra todos antes de o dinheiro sair.
- <!--av:susp_dinheiro-->23<!--/av--> reenvios em conversas com foto suspeita teriam ido ao supervisor antes de qualquer gasto. O custo evitado estimado é de R$ <!--av:susp_custo-->1.356,91<!--/av--> (45% do valor de cada pedido, `docs/parametros.md`). É um valor esperado: suspeita não é fraude confirmada.
- <!--av:obj_n-->93<!--/av--> das <!--av:acoes_total-->790<!--/av--> ações com dinheiro (R$ <!--av:obj_valor-->11.204,37<!--/av-->) o agente não executaria sozinho por regra objetiva: soma acima da alçada, fora do prazo, antes da entrega ou segunda troca.

As divergências que dependem da tag humana da conversa ficam fora dos números acima, porque o relatório as trata como teto.

O ponto fraco medido é o classificador. O leitor de mensagens escolhe a mesma categoria que o atendente em <!--av:cat_acertos-->1595<!--/av--> das <!--av:cat_lidas-->2654<!--/av--> conversas com mensagem do cliente (<!--av:cat_pct-->60,1<!--/av-->%). As categorias com menor acerto são Outros (13,5%), Dúvida (19,3%) e Reclamação de produto (20,2%).

Nos casos sensíveis, o leitor reconhece como reação adversa os 27 relatos que o time registrou em cosmetovigilância no histórico (27 de 27).

Com o Claude, o acerto sobe. Numa amostra de 300 conversas do histórico (estratificada pela tag humana, semente 42), o leitor por regras acerta 161 (53,7%) e o leitor com Claude acerta 186 (62,0%), com as mesmas 27 reações adversas reconhecidas e as 3 instruções embutidas sinalizadas. A execução custou cerca de US$ 2,37 e não caiu nenhuma vez para as regras. Detalhes por categoria em [`ingestao/avaliacao_leitor_claude.md`](ingestao/avaliacao_leitor_claude.md). O Gabriel lê as conversas da fila em paralelo, até 8 por vez, e só depois decide cada caso.

O canal no Slack já rodou com um app real. O Gabriel pediu aprovação para reembolsar R$ 155,81 na conversa AT116520, acima do limite de R$ 100; o supervisor_02 aprovou pelo botão no Slack, e o estorno saiu no gateway simulado com a referência EST000186.

Na fila das 8h (65 conversas), `POST /api/fila/processar` termina com 34 resolvidas sozinho, 2 aguardando aprovação, 18 aguardando foto do cliente, 11 escaladas e nenhuma suspeita. O placar soma R$ 636,00 de custo evitado, que é o custo por conversa do canal (`politicas.csv`) nas 34 resolvidas sem pessoa. A fila não tem reclamação com foto suspeita; a jornada E2E mostra a verificação num caso real do histórico.

A linha de base do problema (custo por canal, recontato, tempo por conversa) está em [`ingestao/baseline_metricas.md`](ingestao/baseline_metricas.md).

## Testes

```bash
uv run pytest -q                 # unitários; cada teste leva o ID do cenário (ex.: test_HG_12_...)
uv run pytest -q -m integracao   # lê a base real em docs/
uv run pytest -q -m llm          # chama o Claude de verdade (precisa de ANTHROPIC_API_KEY)
uv run ruff check .
pnpm --dir web test && pnpm --dir web lint
```

Hoje os 574 testes passam (16 deles de integração), o `ruff` está limpo, os 56 testes do front passam no Vitest e o revisor aprovou 35 das 61 features de [`feature_list.json`](feature_list.json). A jornada no navegador (Playwright) está em [`e2e/README.md`](e2e/README.md): grava prints e vídeo em `.scratch/e2e/` e fecha com 26 de 26 verificações. Os cenários BDD de cada teste estão em [`REQUISITOS.md`](REQUISITOS.md).

## Limitações conhecidas

1. Suspeitas, aprovações, incidentes e o contador de avisos do dia ficam na memória do processo da API. Reiniciar o servidor apaga as pendências.
2. O agente analista detecta cobrança em dobro e contato repetido. Padrões por transportadora e UF, por máquina de personalização e por lote ainda não são detectados (HG-19).
3. Em 59 das 65 conversas da fila, `fila_aberta.csv` não traz `atendente_id`, porque ninguém respondeu ainda. Nesses casos, a aprovação vai ao supervisor do turno.
4. O leitor por regras acerta 60,1% das categorias contra a tag humana. Outros (13,5%) e Dúvida (19,3%) ficam abaixo de 20%, e Reclamação de produto fica em 20,2%. O leitor com Claude melhora a média na amostra de 300, mas ainda erra em Outros (8,3%) e Troca (26,1%).
5. A avaliação offline compara o agente com o que o time fez no histórico. Das escalações, ela mede só os casos de reação adversa.
6. O incidente de contato repetido cobre 453 pedidos e não avisa os clientes.
7. Das 26 features ainda não aprovadas em `feature_list.json` (`"passes": false`), 23 não têm teste com o ID do cenário. EC-25 tem teste só no motor de políticas, HG-13 cobre só a volta às regras quando o leitor falha, e a HG-19 é a lacuna do item 2.
8. O leitor marca como reação adversa qualquer palavra que contenha "ferid", como "preferida". Isso gera escalações a mais, e nenhum caso sensível escapa.
9. O Gabriel não renova o token do Slack. Se o app for criado com rotação de token ligada, o token do bot expira em cerca de 12 h e o canal para de responder até alguém trocar o token no `.env`. O manifesto deixa a rotação desligada.
10. O resumo no Slack sai só ao fim de **Processar fila**. Uma aprovação ou uma suspeita decidida depois não gera resumo novo, e as execuções de rotina não vão ao Slack: ficam no console e no canal do time da tela.

## Estrutura

```
apresentacao/     deck do pitch (abre no navegador; tecla N mostra as notas com as fontes)
prototipo/        visão 360°: mapa das frentes, triagem, canal do time, prevenção
src/atendimento/  agente em Python (ver Arquitetura)
web/              interface da demo (React)
tests/            pytest, com fixtures mínimas em tests/fixtures/
e2e/              jornada Playwright
ingestao/         enunciado, análise de requisitos, linha de base e avaliação offline
decisoes/         ADRs
config/           manifesto do app do Slack
docs/             bases de dados originais (fora do repositório; somente leitura)
var/              banco SQLite gerado (ignorado)
```

- Pitch: [`apresentacao/index.html`](apresentacao/index.html)
- Visão 360°: [`prototipo/index.html`](prototipo/index.html)

Os dados são sintéticos e representam a empresa em 02/11/2026 às 8h.
