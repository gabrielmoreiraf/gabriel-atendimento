# ADR-002: FIO 100% funcional no Vercel com Neon Postgres

## Status

Aceito (decisão do usuário em 2026-11-07)

## Contexto

Até aqui o FIO roda na máquina do autor: FastAPI com SQLite em `var/`, estado do agente em memória (casos, canal, aprovações, suspeitas, eventos), stream SSE, Slack em Socket Mode (conexão WebSocket permanente numa thread) e a base de `docs/` lida do disco. O usuário pediu o app **100% funcional no Vercel, com Neon**.

O modelo serverless do Vercel não guarda estado entre requisições (cada uma pode cair numa instância nova), não mantém conexão permanente e não grava em disco fora de `/tmp`. A URL de produção é pública.

**Mudança na regra dos dados:** a base de `docs/` (dados sintéticos com nome, CPF, e-mail e telefone) deixa de ficar só na máquina do autor e passa a morar num **banco Neon privado**, por decisão do usuário. Ela continua **fora do GitHub** (`docs/` no `.gitignore`) e nunca é servida como arquivo estático.

## Decisão

| Parte | Hoje | No Vercel |
| --- | --- | --- |
| Base de dados | SQLite gerado de `docs/` | Neon Postgres, carregado uma vez por script local (`DATABASE_URL`) |
| Estado do agente | memória do processo | tabelas no Neon (casos, canal, aprovações, suspeitas, eventos, incidentes, contador de avisos) |
| Trava da rodada | `threading.RLock` | advisory lock do Postgres |
| Eventos ao vivo | SSE do barramento em memória | SSE lendo a tabela de eventos (`?desde=`), com reconexão e fallback de polling |
| Slack | Socket Mode (thread + WebSocket) | modo HTTP: `/api/slack/eventos` com verificação de assinatura (`SLACK_SIGNING_SECRET`); postagem feita na própria requisição que gera a mensagem |
| Interface | Vite em `localhost:5173` | build estático no Vercel, mesma origem da API |
| Acesso | local | **senha obrigatória** (Basic Auth por Routing Middleware) em tudo, exceto `/api/slack/eventos`, que é autenticado pela assinatura do Slack |
| Reiniciar a demo | reiniciar o backend | `POST /api/demo/reiniciar` (protegido) limpa o estado do agente sem recarregar a base |

SQLite continua sendo o banco dos testes unitários e do modo local: a camada de dados fala com os dois.

## Alternativas consideradas

- **Só a interface no Vercel (modo demonstração):** sem dados nem chaves fora da máquina, mas não é "100% funcional". Rejeitada pelo usuário.
- **API local exposta por túnel:** dados locais, mas depende da máquina ligada. Rejeitada.
- **Backend em plataforma com processo contínuo (Railway, Render, Fly):** manteria Socket Mode e memória, mas o usuário escolheu Vercel + Neon.

## Consequências

- Refatoração do estado do agente para o banco; risco de regressão controlado pela suíte (552 testes) rodando em SQLite e uma bateria no Postgres.
- A rodada da fila precisa caber no tempo máximo de função do plano Hobby; a leitura com Claude já é paralela.
- Custo: com `ATENDIMENTO_LLM=1`, cada rodada consome a API da Anthropic; a senha da demo protege contra uso por terceiros.
- O Slack muda de configuração: Socket Mode desligado, Request URL apontando para o domínio do Vercel; o App-Level Token (`xapp`) deixa de ser necessário e entra o Signing Secret.
- Dados pessoais passam a existir num serviço de terceiros (Neon); o acesso ao banco fica só nas variáveis de ambiente do Vercel e no `.env` local.
