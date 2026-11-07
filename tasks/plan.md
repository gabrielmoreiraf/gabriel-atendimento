# Plano de implementação — MVP (entrega 12h de 07/11/2026)

Spec: `SPEC.md`. Contratos: `src/atendimento/contratos.py`. Maestro: a sessão Claude principal (coordena, integra, registra em `progress.md`, chama o `revisor`).

## Dependências

```
contratos.py (pronto)
  ├── W1 dados + ferramentas ──┐
  ├── W2 politicas ────────────┼──> W4 agente + API ──> W5 web (usa mocks até a API subir)
  └── W3 verificacao ──────────┘                          └──> E2E (maestro, 11:40)
```

W1, W2, W3 e W5 começam juntos. W4 começa pelo leitor de mensagens e pelo esqueleto da API (sem depender de ninguém) e integra W1–W3 conforme ficam prontos.

## Posse de arquivos (pasta sem git: posse exclusiva evita conflito)

| Worker | Pode criar e editar | Cenários principais |
| --- | --- | --- |
| W1 Dados e ferramentas | `src/atendimento/dados/**`, `src/atendimento/ferramentas/**`, `tests/test_dados_*.py`, `tests/test_ferramentas_*.py`, `tests/fixtures/dados/**` | EC-21, HG-02, HG-12, HP-08, HP-09 |
| W2 Políticas | `src/atendimento/politicas/**`, `tests/test_politicas_*.py`, `tests/fixtures/politicas/**` | EC-01, EC-02, EC-03, HG-03, HG-04, HG-05, HG-06, HG-08, HG-22, EC-22 |
| W3 Verificação | `src/atendimento/verificacao/**`, `tests/test_verificacao_*.py`, `tests/fixtures/verificacao/**` | EC-15, EC-16, EC-17, EC-18, EC-19, HG-07 |
| W4 Agente e API | `src/atendimento/agente/**`, `src/atendimento/api/**`, `tests/test_agente_*.py`, `tests/test_api_*.py`, `tests/fixtures/agente/**` | HP-01, HP-04, HP-10, HG-09, HG-11, EC-20, HG-01 |
| W5 Interface | `web/**`, `tokens.css`, `DESIGN.md` | HP-10 (tela), demo |
| Maestro | `contratos.py`, `pyproject.toml`, `uv.lock`, `SPEC.md`, `tasks/**`, `progress.md`, `AGENTS.md` | integração, E2E, revisão |

Ninguém além do maestro roda `uv add`, `graphify update .` ou edita `progress.md`. Só o `revisor` muda `feature_list.json`.

## Cronograma

| Hora | Marco |
| --- | --- |
| 10:45 | Workers W1–W5 iniciados |
| 11:20 | **Checkpoint 1:** W1, W2, W3 entregam módulos com testes verdes; W4 tem o leitor e a API com dados reais via W1 |
| 11:35 | **Checkpoint 2:** W4 integra política + verificação; `POST /api/fila/processar` trata as 65 conversas; W5 conectado à API real |
| 11:45 | E2E (Playwright) gravado em `.scratch/e2e/` |
| 11:50 | `/review` + `revisor` marcam as features aprovadas |
| 12:00 | Entrega |

## Riscos

| Risco | Impacto | Mitigação |
| --- | --- | --- |
| Integração tardia de W4 | Alto | Contratos fixos em `contratos.py`; W4 usa os módulos assim que cada worker reportar |
| Dois workers no mesmo arquivo | Alto | Posse exclusiva acima; pedir ao maestro |
| Slack sem token | Médio | Canal do time na própria interface (SPEC, Q8) |
| Sem chave de LLM | Baixo | Leitor determinístico atrás de uma interface |
