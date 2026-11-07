# Plano: FIO no Vercel + Neon (ADR-002)

Objetivo: o FIO 100% funcional em produção no Vercel (projeto `fio-atendimento`, Neon `fio-neon` já provisionado e conectado; `DATABASE_URL` no Vercel e no `.env.local`). Branch: `feature/vercel-neon` (o maestro cria quando W4 e W1 terminarem; até lá **não commite**, só edite).

## Contratos entre workers

1. **Banco (W3):** `atendimento.dados.banco` expõe `conectar(url: str | None) -> Banco`.
   - `url` começando com `postgres` → Postgres (psycopg 3, já instalado); senão, SQLite (caminho de arquivo). Sem url: `DATABASE_URL` do ambiente, senão `var/atendimento.db`.
   - `Banco.executar(sql, params=()) -> list[dict]` e `Banco.executar_um(...) -> dict | None`, SQL **sempre com `?`** (o Banco traduz para `%s` no Postgres); `Banco.transacao()` (context manager); `Banco.trava(nome)` (context manager: `pg_advisory_lock` no Postgres, `threading.Lock` no SQLite); `Banco.dialeto` (`"sqlite"`/`"postgres"`).
   - `Base` e `Ferramentas` passam a usar o `Banco`; a interface pública deles não muda.
   - W3 publica o esqueleto (SQLite funcionando) em até 15 min e avisa o maestro, que repassa a todos.
2. **Estado do agente (W4):** casos, canal, aprovações, suspeitas, eventos, incidentes e contadores saem da memória para tabelas criadas pelo W3 a pedido do W4 (W4 manda o DDL portátil ao W3, ou cria em `atendimento.agente.estado` usando só `Banco.executar`). Eventos numa tabela `eventos(id serial, tipo, payload json, criado_em)`; `/api/eventos?desde=<id>` lê dela. Rodada da fila protegida por `Banco.trava("rodada")`. `POST /api/demo/reiniciar` limpa o estado sem recarregar a base.
3. **Slack HTTP (W2):** `POST /api/slack/eventos` (eventos + interatividade) com verificação de assinatura (`SLACK_SIGNING_SECRET`), Bolt em modo FaaS (`process_before_response=True`). Postagem e `chat_update` na própria requisição que grava a mensagem do canal (sem thread); `ts` da mensagem do Slack guardado no banco. `ATENDIMENTO_SLACK_MODO=http|socket` (padrão `http` quando `VERCEL` está definido; `socket` local).
4. **Vercel e interface (W5):** configuração do projeto (Python + Vite numa origem só, `/api/*` → FastAPI), Routing Middleware com Basic Auth (`DEMO_USUARIO`/`DEMO_SENHA`) em tudo **exceto** `/api/slack/eventos`; front com SSE reconectando por `desde` e fallback de polling; botão "Reiniciar demo".
5. **Maestro:** variáveis no Vercel (sem ecoar valores), carga da base no Neon, deploy, Slack em modo HTTP.

## Pronto quando

- Suíte padrão verde em SQLite; bateria `-m postgres` verde contra o Neon (`DATABASE_URL` do `.env.local`).
- `vercel deploy` sobe; com senha, a jornada E2E passa contra a URL do Vercel.
- Slack: aprovação por botão funciona contra a URL do Vercel.
