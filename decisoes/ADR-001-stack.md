# ADR-001: Python no agente, React só na interface da demo

## Status

Aceito

## Data

2026-11-07

## Contexto

O `AGENTS.md` define Python como padrão para análise e backend do agente, "salvo decisão registrada". A PoC precisa de três coisas além do backend:

- mostrar que o agente **age** nos sistemas (o anti-requisito N4 reprova "um painel bonito que mostra o problema, mas não age");
- simular o lado do cliente (WhatsApp, e-mail, Reclame Aqui), já que os canais reais não estão disponíveis;
- ter um alvo estável para o E2E da camada 5. Fazer login no Slack dentro do Playwright é frágil, e a demo não pode depender do Wi-Fi do evento.

As regras de negócio (alçada, suspeita, política) precisam de TDD com o ID do cenário de `REQUISITOS.md`, e `uv`, `pytest` e `ruff` já estão configurados.

## Decisão

Duas stacks com fronteira rígida: **toda regra de negócio em Python; o React só exibe e dispara ações pela API.**

| Parte | Stack |
| --- | --- |
| Motor de políticas, verificador de evidência, ferramentas | Python ≥ 3.12, stdlib + `pydantic` |
| Sistemas simulados | SQLite gerado a partir dos CSVs, fora de `docs/` |
| API do agente | `fastapi` + SSE para eventos ao vivo |
| LLM | SDK `anthropic` (Claude): só lê a mensagem e redige a resposta; a decisão é do motor de políticas (N2) |
| Canal do time | `slack-bolt` em Socket Mode, **se Q8 confirmar Slack** |
| Interface da demo | React + Vite + TypeScript, com `pnpm`, consumindo `tokens.css` |
| Testes | `pytest` (backend), Vitest (front), Playwright (E2E) |
| Lint do front | Biome (lint e formatação) |

O React cobre três telas: o simulador do cliente, o console das ações executadas nos sistemas (com o ID de cada registro) e a caixa de aprovação do supervisor, que serve de plano B se o Slack falhar.

## Alternativas consideradas

### Só Python (Streamlit ou páginas servidas pelo FastAPI)

- Prós: uma stack só e um gerenciador de pacotes.
- Contras: o Streamlit dá pouco controle de layout para simular um chat e acompanhar ações ao vivo; o resultado tende a parecer dashboard, que é o que o N4 reprova.
- Rejeitada: a demo é a principal evidência de que o agente age.

### Next.js

- Prós: framework completo, com deploy fácil na Vercel.
- Contras: SSR e rotas de servidor duplicariam o papel do FastAPI e abririam espaço para lógica de negócio em TypeScript.
- Rejeitada: o Vite é suficiente para uma SPA que só consome a API.

### Backend em Node/TypeScript

- Rejeitada: jogaria fora o ambiente `uv` + `pytest` + `ruff` já montado e os scripts da camada 1.

## Consequências

- Dois gerenciadores de pacotes (`uv` e `pnpm`) e dois linters (`ruff` e Biome). Os comandos ficam no `AGENTS.md`.
- **Nenhuma regra de negócio no React.** Se um teste de cenário de `REQUISITOS.md` precisar de lógica no front, a lógica está no lugar errado.
- As versões são fixadas no `/build`, com `uv add` e `pnpm add`, e registradas em `uv.lock` e `pnpm-lock.yaml`.
- A integração com o canal depende da Q8. Se a escolha for Telegram, este ADR é substituído só na linha do canal.
- O alvo do E2E passa a ser a interface React com o backend FastAPI. O comando exato fica no `SPEC.md`.
