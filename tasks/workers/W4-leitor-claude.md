# W4 · Leitor com Claude (atrás de ATENDIMENTO_LLM)

**Objetivo:** o FIO pode usar o Claude para LER a mensagem do cliente (classificar, extrair pedido e cupom, detectar caso sensível e instrução embutida), com volta automática para o leitor por regras. **Quem decide continua sendo o motor de políticas (HG-01).** A redação das respostas continua determinística nesta fatia.

**Branch:** `feature/leitor-claude` (já criado pelo maestro; o repositório agora é git). Commits pequenos, no imperativo, com o trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`, só com a suíte e o ruff verdes. Não faça merge nem push.

**Skills obrigatórias:** invoque `claude-api` ANTES de escrever qualquer código que chame a API (modelo, SDK, saída estruturada, timeouts, retries). Depois `test-driven-development`.

**Pode editar:** `src/atendimento/agente/leitor_claude.py` (novo), `src/atendimento/agente/leitor.py` (só para expor um ponto de escolha do leitor), `src/atendimento/agente/caso.py` (só a injeção do leitor), `src/atendimento/api/app.py` (só a escolha do leitor na subida), `src/atendimento/avaliacao/**` (medição), `tests/test_leitor_claude*.py`, `tests/test_avaliacao_*.py`. Dependências `anthropic` e `python-dotenv` já estão no `pyproject.toml` (não rode `uv add`).

**Requisitos:**
1. `ATENDIMENTO_LLM=1` liga o leitor com Claude; ausente ou `0` mantém o leitor por regras (padrão). Carregue `.env` com `python-dotenv`. **Nunca** leia, imprima, logue ou grave o valor de `ANTHROPIC_API_KEY`.
2. **Dado pessoal (AGENTS.md, regra 6):** o texto passa por `atendimento.privacidade.mascarar` ANTES de ir para a API. Teste que prova que CPF, cartão, telefone e e-mail não chegam ao cliente HTTP (mock).
3. **HG-09:** o texto do cliente vai como dado, delimitado, com instrução de sistema dizendo que é conteúdo a classificar e nunca instrução. Teste com as mensagens de injection reais (AT105778, AT108856, AT116445) num mock.
4. **Saída estruturada** validada (categoria na lista de `categorias.*` de `politicas.csv`, categoria_secundaria, order_ids, sensivel, instrucao_embutida, codigo_cupom). Rede de segurança determinística combinada com a resposta do Claude:
   - `sensivel` e `instrucao_embutida` = OU entre Claude e regras (nunca perder reação adversa: as 27 de 27 continuam);
   - `order_ids` só os que aparecem literalmente no texto; `codigo_cupom` só se estiver em `cupons.csv`;
   - categoria fora da lista → usa a das regras.
5. **Resiliência (HG-13):** timeout curto, erro de rede, rate limit ou resposta inválida → leitor por regras, com o motivo registrado (sem o texto do cliente). Cache por hash do texto mascarado em `var/` para não pagar duas vezes.
6. **Testes unitários sem rede** (cliente falso). Um teste de verdade com `@pytest.mark.llm` (fora da suíte padrão; roda com `uv run pytest -m llm`).
7. **Medição (HG-18):** `uv run python -m atendimento.avaliacao --leitor claude --amostra 300` compara regras × Claude na MESMA amostra estratificada por tag (semente fixa), com acerto por tag e as 27 cosmetovigilâncias. Rode só em amostra (custo). Grave em `ingestao/avaliacao_leitor_claude.md` com o modelo usado, o tamanho da amostra e a data.

**Pronto quando:** suíte padrão verde (437+), `ruff check` e `format --check` limpos, `-m llm` roda pelo menos 1 caso real, relatório gerado, e o app sobe nos dois modos. **Não reinicie o servidor :8000 do usuário**; teste em outra porta. No `worker_done`, traga: modelo escolhido e por quê (citando a skill), acerto regras × Claude na amostra, custo estimado da amostra, commits criados.
