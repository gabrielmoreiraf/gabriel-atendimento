## Regras comuns a todos os workers (leia antes de começar)

- Projeto: `/Users/gabrielmoreira/Documents/gohacks/atendimento_ao_cliente`. Leia `AGENTS.md`, `SPEC.md`, `tasks/plan.md` e `src/atendimento/contratos.py` antes de codar. Os requisitos BDD estão em `REQUISITOS.md` (procure pelos `@id` dos seus cenários).
- **Prazo duro: entregar até 11:20** (relógio local). Prefira um núcleo menor, testado e funcionando a algo grande e quebrado. Às 11:15, pare de abrir frentes e feche o que tem.
- **Posse de arquivos:** edite SOMENTE os caminhos listados na sua tarefa. Outros workers trabalham na mesma pasta ao mesmo tempo, e ela não tem git. Se precisar mudar `contratos.py`, `pyproject.toml` ou arquivo de outro worker, pergunte ao maestro com `ask`. Não rode `uv add`, `graphify update .`, nem edite `progress.md` ou `feature_list.json`.
- **Skills obrigatórias (camada 4):** invoque `test-driven-development` e `incremental-implementation` antes de codar. Red-Green-Refactor: o teste falha antes da implementação. Cada teste leva o ID do cenário (`test_EC_01_...`).
- **Dados:** `docs/` é somente leitura. Joins por ID. CSVs em UTF-8, separador `,` (confirme). "Agora" = `contratos.AGORA` (02/11/2026 08:00, America/Sao_Paulo), nunca o relógio do sistema. Custos e limites vêm de `docs/politicas.csv` e `docs/parametros.md`. Não invente números.
- **Dados pessoais:** CPF, cartão, telefone e e-mail nunca em logs, respostas ou fixtures sem máscara.
- **Antes de reportar:** `uv run pytest -q` e `uv run ruff check .` verdes (rode também `uv run ruff format` só nos seus arquivos). Se um teste de outro worker estiver vermelho, não mexa: só cite no relatório.
- **Relatório final (`worker_done`):** arquivos criados, cenários cobertos (IDs), saída resumida do pytest e do ruff, a API pública do seu módulo (assinaturas) e o que ficou de fora.
