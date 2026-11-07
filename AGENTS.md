# AGENTS.md — Atendimento ao Cliente (GoHacks Talent 2026)

Regras para qualquer agente (Claude, Codex, Cursor etc.) e pessoa que trabalhe neste repositório.

## Arquitetura fixa (vale para QUALQUER ação)

Toda tarefa, por menor que seja, segue os 3 pilares e passa pela camada de skill correspondente. Pular uma camada exige registrar o motivo em `progress.md`.

### Os 3 pilares

1. **Harness (andaime e governança).** Este `AGENTS.md` e o `CLAUDE.md` definem o que a IA vê, o que pode alterar e as regras de segurança. Nenhuma tarefa é concluída com teste vermelho. `.claude/settings.json` bloqueia escrita em `docs/`.
2. **Loop Engineering (ciclo autônomo de resolução).** O trabalho é guiado por metas:
   - `feature_list.json`: cada feature (cenário de `REQUISITOS.md`) começa com `"passes": false`;
   - `progress.md`: registro de cada avanço (data, feature, camada, skill usada, resultado, evidência);
   - `.claude/agents/revisor.md`: subagente revisor, **separado do executor**. Só ele marca `"passes": true`.
3. **Graph Engineering (mapeamento e rastreabilidade).** Antes de qualquer alteração de código, rode `graphify update .` (AST local, sem LLM) e consulte o impacto com `graphify affected "<símbolo>"` / `graphify query "<pergunta>"`. Saídas em `graphify-out/` (ignorado).

### As 6 camadas e a skill obrigatória de cada uma

| Camada | Skill / ferramenta | Uso obrigatório |
| --- | --- | --- |
| 1. Ingestão e requisitos | `markitdown` + awesome-qa-skills (`requirements-analysis`, `test-strategy`, `change-impact-analysis`, `bug-reporting`) | Converter briefings e dados para Markdown; estruturar requisitos em BDD (Given-When-Then) no `REQUISITOS.md`; registrar defeitos com `bug-reporting` |
| 2. Design e UI | designer-skills (`designer-toolkit:*`, `ui-design:*`, `design-systems:*`) + `impeccable` | Especificar telas e gerar os slides com `/designer-toolkit:build-presentation`; auditar o visual contra `tokens.css` e `DESIGN.md` com `impeccable` (ainda não existem: são criados na raiz nesta camada, quando a UI for especificada) |
| 3. Mapeamento de código | `graphify` | Grafo pela AST antes de editar; prever impacto antes de mudar |
| 4. Engenharia e TDD | agent-skills (`spec-driven-development`, `planning-and-task-breakdown`, `incremental-implementation`, `test-driven-development`, `code-review-and-quality`) | Fluxo `/spec` → `/plan` → `/build` → `/review`; Red-Green-Refactor: o teste é escrito e falha antes da implementação |
| 5. Validação E2E e mídia | `playwright-skill` | Jornada completa do MVP no navegador, com screenshots e vídeo `.mp4` em `.scratch/e2e/` |
| 6. Review e entrega | `code-review-and-quality` (`/review`) + subagente `revisor` + `humanizer` | Revisão do código e aprovação do `revisor` antes de `"passes": true`; revisar com `humanizer` o `README.md`, o pitch, o texto de submissão e o Relatório Individual antes da versão final |

### Fluxo de execução de cada ordem

1. **Harness:** ler este arquivo e aplicar as restrições.
2. **Camada:** identificar a camada da tarefa e invocar a skill correspondente.
3. **Grafo:** se a tarefa toca código, `graphify update .` e consulta de impacto antes de editar.
4. **Loop:** pegar a próxima feature com `"passes": false` em `feature_list.json`, escrever o teste que falha, implementar, rodar `uv run pytest -q` e `uv run ruff check .`.
5. **E2E:** jornada no navegador com `playwright-skill`, evidências em `.scratch/e2e/`.
6. **Review:** `/review` e depois o subagente `revisor`. Se ele aprovar, ele marca `"passes": true` e o executor registra em `progress.md`. Texto final com `humanizer`.

As skills ficam em `~/.agents/skills/` e `~/.claude/skills/`, com atalhos do projeto em `.claude/skills/`.

## Contexto

- Desafio **Atendimento ao Cliente** do GoHacks Talent 2026: e-commerce Gocase / GoBeauté.
- O enunciado oficial está em `ingestao/desafio/enunciado.md`. Não existe PDF do desafio.
- `docs/` contém as bases de dados (24 CSVs sintéticos), `README.md` (mapa desafio → dados), `dicionario_de_dados.md` (colunas) e `parametros.md` (custos em R$ e premissas). **Leia esses três arquivos antes de escrever código ou tirar conclusões.**
- Requisitos e critérios de aceite: `REQUISITOS.md`. Versões em Markdown das bases: `ingestao/markdown/`.
- Os dados representam a empresa em **02/11/2026 às 08h**. Esse é o "agora" do projeto: não trate datas posteriores como passado, e não use o relógio do sistema como referência.
- As tabelas se ligam por ID, como num banco relacional. Faça joins pelos IDs documentados no dicionário, nunca por nome ou texto livre.

## Stack, comandos e caminhos

| Item | Valor |
| --- | --- |
| Decisão de stack | `decisoes/ADR-001-stack.md`: Python no agente, React só na interface da demo. **Nenhuma regra de negócio no front** |
| Backend (agente) | Python ≥ 3.12 (venv local em `.venv/`, hoje com 3.14): motor de políticas, verificador, ferramentas, `fastapi` + SSE, SQLite gerado dos CSVs, SDK `anthropic`, `slack-bolt` (se Q8 = Slack) |
| Frontend (demo) | React + Vite + TypeScript em `web/` (**a criar no `/build`**), com `pnpm` (Node 22); consome `tokens.css` |
| Projeto e dependências | Python: `pyproject.toml` + `uv.lock` via `uv` (`uv add <pacote>`, `uv add --dev <pacote>`). Front: `web/package.json` + `pnpm-lock.yaml` via `pnpm add` |
| Instalar ambiente | `uv sync` e `pnpm --dir web install` |
| Testes unitários | `uv run pytest -q` (em `tests/`, fixtures em `tests/fixtures/`); front: `pnpm --dir web test` (Vitest) |
| Testes em paralelo | `uv run pytest -n auto` (`pytest-xdist`) |
| Testes de integração | `uv run pytest -q -m integracao` (marcador registrado no `pyproject.toml`) |
| Lint e formatação | `uv run ruff check .` e `uv run ruff format --check .` (E501 desligado; o comprimento fica com o `ruff format`); front: `pnpm --dir web lint` (Biome) |
| E2E | `playwright-skill` (Playwright e Chromium já instalados na skill). Alvo: a interface React com o backend FastAPI; comando **a definir no `/spec`** |
| Scripts da camada 1 | `python3 -I ingestao/baseline_metricas.py`, `python3 -I ingestao/gerar_feature_list.py` |
| Grafo | `graphify update .`, `graphify affected "<símbolo>"`, `graphify query "<pergunta>"` |
| Requisitos | `REQUISITOS.md` (BDD), `ingestao/analise_requisitos.md`, `ingestao/desafio/enunciado.md` |
| Mapa dos dados | `docs/README.md`, `docs/dicionario_de_dados.md`, `docs/parametros.md` |
| Design system | `tokens.css` e `DESIGN.md` na raiz, **a criar na camada 2** |
| README do projeto | `README.md` na raiz, **a criar** na entrega (camada 6) |
| Git | a pasta ainda **não é um repositório git** |

## Regras de dados

1. **`docs/` é somente leitura.** Nunca edite, sobrescreva, renomeie ou "limpe" os CSVs originais. Transformações geram arquivos novos fora de `docs/`.
2. **Sem números inventados.** Toda métrica, valor em R$ ou contagem apresentada precisa vir de uma consulta reproduzível sobre os CSVs. Cite o arquivo e as colunas usadas.
3. **Custos e limites vêm de `parametros.md` e `politicas.csv`.** Não use valores de mercado ou suposições quando o parâmetro existir no repositório.
4. **Confira a reclamação antes de agir.** Qualquer decisão automática (reenvio, estorno, cupom) deve checar pedido, item, personalização, data de entrega, anexos e histórico de reenvios do cliente, conforme o README.
5. **Respeite papéis e alçadas.** O que o agente pode fazer sozinho é definido por `ferramentas.csv` e pelos limites por papel em `politicas.csv`. Fora disso, escale para uma pessoa (`equipe_atendimento.csv`).
6. **Dados pessoais.** Mesmo sintéticos, CPF, e-mail e telefone não vão para logs, prints de apresentação, prompts de serviços externos ou commits de exemplo. Mascare (`***.***.***-12`).
7. **Encoding e separador.** Leia os CSVs como UTF-8 e confirme o separador de cada arquivo antes de processar.

## Regras de desenvolvimento

- **Fluxo:** `/spec` → `/plan` → `/build` → `/review` (camada 4). Mudança não trivial começa com spec (`SPEC.md`) e plano (`tasks/plan.md`).
- **Fatias pequenas e verificáveis:** uma feature de `feature_list.json` por vez, com teste, antes de seguir.
- **Python como padrão** para análise e backend do agente; React + TypeScript só na interface da demo (`decisoes/ADR-001-stack.md`). Outras exceções exigem um novo ADR em `decisoes/`. Dependências fixadas em `pyproject.toml` + `uv.lock` (via `uv add`) e em `web/pnpm-lock.yaml` (via `pnpm add`). Nada de instalação global sem registro.
- **Segredos** (chaves de API, tokens) apenas em `.env`, que nunca é commitado. Mantenha um `.env.example` atualizado.
- **Commits** pequenos, com mensagem descritiva no imperativo. Não faça commit de `.scratch/`, `graphify-out/` ou saídas geradas.
- Rascunhos, arquivos temporários e mídias de E2E ficam em `.scratch/`.

## Regras de testes

- **TDD para lógica de negócio:** regras de política, cálculo de custo, verificação de reclamação e decisão automático/humano começam com um teste que falha.
- **Testes não dependem do relógio.** Fixe "agora" em `2026-11-02T08:00:00` (America/Sao_Paulo).
- **Fixtures pequenas:** testes unitários usam recortes mínimos dos CSVs em `tests/fixtures/`, não a base inteira. Testes de integração podem ler `docs/` em modo leitura.
- **Cobertura obrigatória para:** limites em R$ por papel, casos sensíveis (reação adversa, reclamação suspeita), detecção de contatos repetidos e cobranças em dobro.
- **Rodar antes de cada commit e antes de marcar uma feature:** `uv run pytest -q` e `uv run ruff check .` (use `uv run pytest -n auto` quando a suíte crescer). Um teste vermelho bloqueia o commit; nunca use skip, delete ou afrouxe um teste para ficar verde.
- **Rastreio teste ↔ requisito:** cada teste leva o ID do cenário de `REQUISITOS.md` (ex.: `test_EC_01_limite_reembolso`).
- **E2E / demo:** `playwright-skill`; vídeo `.mp4`, screenshots e relatórios em `.scratch/e2e/`.

## Definição de pronto

Uma feature está pronta quando: o teste com o ID do cenário passa, `uv run pytest -q` e `uv run ruff check .` estão verdes, cada número tem origem rastreável em `docs/`, nenhuma regra de política foi violada, e o subagente `revisor` aprovou e marcou `"passes": true` em `feature_list.json`, com registro em `progress.md`.
