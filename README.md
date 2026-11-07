# FIO, o colega de atendimento (Gocase / GoBeauté)

GoHacks Talent 2026, desafio **Atendimento ao Cliente**.

FIO é um agente que trabalha a fila de atendimento como um colega do time. O nome vem de seguir o fio do pedido pelos sistemas. Ele lê a conversa, consulta pedido, pagamento, rastreio e anexos por ID e confere se a foto da reclamação é daquele pedido. Depois aplica a política e age nos sistemas quando a ação cabe na alçada. Quando não cabe, ou quando o caso é sensível ou suspeito, ele chama o supervisor do turno no canal do time, com o pedido, o valor e as evidências.

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

Sem `docs/`, rode `uv run pytest -m "not integracao"`: os 428 testes unitários usam recortes mínimos e sem dado pessoal em `tests/fixtures/`. Os 9 testes de integração (`-m integracao`) leem a base e só passam com ela.

## Como rodar

Pré-requisitos: [`uv`](https://docs.astral.sh/uv/), Node 22 e `pnpm`.

```bash
uv sync
uv run uvicorn atendimento.api.app:app --port 8000
pnpm --dir web install && pnpm --dir web dev   # abre em http://localhost:5173
```

Rode o segundo e o terceiro comandos em terminais separados. Na primeira subida, a API gera `var/atendimento.db` a partir dos CSVs de `docs/`, que ela só lê. Para gerar a base à mão: `uv run python -m atendimento.dados.carga`.

Na tela, **Processar fila** trata as 65 conversas abertas às 8h de 02/11/2026, o "agora" do projeto. O console mostra cada ação executada e o canal do time mostra os pedidos de aprovação.

## Arquitetura

Toda regra de negócio está em Python. O React só exibe o que a API devolve e dispara ações. A decisão está registrada em [`decisoes/ADR-001-stack.md`](decisoes/ADR-001-stack.md).

| Módulo | Papel |
| --- | --- |
| `src/atendimento/contratos.py` | dataclasses compartilhadas entre os módulos e o "agora" fixo |
| `src/atendimento/dados/` | carga dos CSVs num SQLite e leitura por ID (pedido, anexos, histórico de ações) |
| `src/atendimento/ferramentas/` | ferramentas de `docs/ferramentas.csv` com efeito nos sistemas simulados e log de ações |
| `src/atendimento/politicas/` | motor de políticas: executar, pedir aprovação, sinalizar suspeita, escalar ou negar |
| `src/atendimento/verificacao/` | verificador de evidência da reclamação (hash, data de captura, editor, personalização) |
| `src/atendimento/agente/` | leitura da mensagem, priorização da fila, orquestração do caso e aprovações |
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
- Travas nas ferramentas. A ferramenta recusa e registra a chamada de um papel sem permissão em `ferramentas.csv`. Uma ação com dinheiro repetida devolve o registro existente, sem pagar duas vezes.

## Resultados medidos

[`ingestao/avaliacao_offline.md`](ingestao/avaliacao_offline.md) reexecuta o motor de políticas e o verificador sobre as ações com dinheiro que o time já executou (`uv run python -m atendimento.avaliacao`):

- <!--av:m11_barrados-->64<!--/av--> de <!--av:m11_total-->64<!--/av--> casos em que cada ação cabia na alçada, mas a soma no pedido passou do limite sem aprovação. O motor barra todos antes de o dinheiro sair.
- <!--av:susp_dinheiro-->23<!--/av--> reenvios em conversas com foto suspeita teriam ido ao supervisor antes de qualquer gasto. O custo evitado estimado é de R$ <!--av:susp_custo-->1.356,91<!--/av--> (45% do valor de cada pedido, `docs/parametros.md`). É um valor esperado: suspeita não é fraude confirmada.
- <!--av:obj_n-->93<!--/av--> das <!--av:acoes_total-->790<!--/av--> ações com dinheiro (R$ <!--av:obj_valor-->11.204,37<!--/av-->) o agente não executaria sozinho por regra objetiva: soma acima da alçada, fora do prazo, antes da entrega ou segunda troca.

As divergências que dependem da tag humana da conversa ficam fora dos números acima, porque o relatório as trata como teto.

O ponto fraco medido é o classificador. O leitor de mensagens escolhe a mesma categoria que o atendente em <!--av:cat_acertos-->1595<!--/av--> das <!--av:cat_lidas-->2654<!--/av--> conversas com mensagem do cliente (<!--av:cat_pct-->60,1<!--/av-->%). As categorias com menor acerto são Outros (13,5%), Dúvida (19,3%) e Reclamação de produto (20,2%).

Nos casos sensíveis, o leitor reconhece como reação adversa os 27 relatos que o time registrou em cosmetovigilância no histórico (27 de 27).

Na fila das 8h (65 conversas), `POST /api/fila/processar` termina com 34 resolvidas sozinho, 2 aguardando aprovação, 18 aguardando foto do cliente, 11 escaladas e nenhuma suspeita. O placar soma R$ 636,00 de custo evitado, que é o custo por conversa do canal (`politicas.csv`) nas 34 resolvidas sem pessoa. A fila não tem reclamação com foto suspeita; a jornada E2E mostra a verificação num caso real do histórico.

A linha de base do problema (custo por canal, recontato, tempo por conversa) está em [`ingestao/baseline_metricas.md`](ingestao/baseline_metricas.md).

## Testes

```bash
uv run pytest -q                 # unitários; cada teste leva o ID do cenário (ex.: test_HG_12_...)
uv run pytest -q -m integracao   # lê a base real em docs/
uv run ruff check .
pnpm --dir web test && pnpm --dir web lint
```

Na entrega, os 437 testes passam (9 deles de integração), o `ruff` está limpo, os 49 testes do front passam no Vitest e o revisor aprovou 34 das 61 features de [`feature_list.json`](feature_list.json). A jornada no navegador (Playwright) está em [`e2e/README.md`](e2e/README.md): grava prints e vídeo em `.scratch/e2e/` e fecha com 26 de 26 verificações. Os cenários BDD de cada teste estão em [`REQUISITOS.md`](REQUISITOS.md).

## Limitações conhecidas

1. Suspeitas, aprovações, incidentes e o contador de avisos do dia ficam na memória do processo da API. Reiniciar o servidor apaga as pendências.
2. O agente analista detecta cobrança em dobro e contato repetido. Padrões por transportadora e UF, por máquina de personalização e por lote ainda não são detectados (HG-19).
3. Em 59 das 65 conversas da fila, `fila_aberta.csv` não traz `atendente_id`, porque ninguém respondeu ainda. Nesses casos, a aprovação vai ao supervisor do turno.
4. O leitor de mensagens acerta 60,1% das categorias contra a tag humana. Outros (13,5%) e Dúvida (19,3%) ficam abaixo de 20%, e Reclamação de produto fica em 20,2%.
5. A avaliação offline compara o agente com o que o time fez no histórico. Das escalações, ela mede só os casos de reação adversa.
6. O incidente de contato repetido cobre 453 pedidos e não avisa os clientes.
7. Das 27 features ainda não aprovadas em `feature_list.json` (`"passes": false`), 25 não têm teste com o ID do cenário. EC-25 tem teste só no motor de políticas, e a HG-19 é a lacuna do item 2.
8. O leitor marca como reação adversa qualquer palavra que contenha "ferid", como "preferida". Isso gera escalações a mais, e nenhum caso sensível escapa.

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
docs/             bases de dados originais (fora do repositório; somente leitura)
var/              banco SQLite gerado (ignorado)
```

- Pitch: [`apresentacao/index.html`](apresentacao/index.html)
- Visão 360°: [`prototipo/index.html`](prototipo/index.html)

Os dados são sintéticos e representam a empresa em 02/11/2026 às 8h.
