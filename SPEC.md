# SPEC — MVP do agente de atendimento (prazo: 02/11 no evento, entrega 12h)

Requisitos completos: `REQUISITOS.md`. Stack: `decisoes/ADR-001-stack.md`. Plano e posse de arquivos: `tasks/plan.md`.

## Objetivo

Provar a frente **F3 + F4** (verificar a reclamação e decidir sozinho ou escalar), com **F2** executando a ação no fim. O agente pega a fila aberta das 08h (`fila_aberta.csv`, 65 conversas), lê cada caso, confere a evidência, consulta a política e:

- **age** nos sistemas simulados quando a ação cabe na alçada (reenvio, reimpressão, troca até R$ 200; reembolso até R$ 100), deixando registro no log;
- **pede aprovação** no canal do time quando passa da alçada, com o supervisor do turno;
- **sinaliza suspeita** com as evidências quando a foto não bate (hash repetido, captura antes da entrega, editor, personalização divergente), sem acusar o cliente;
- **escala** os casos sensíveis (reação adversa: orientar suspensão + cosmetovigilância).

## Decisões fechadas (Q do `REQUISITOS.md` §4)

| Q | Decisão |
| --- | --- |
| Q1 | PoC = F3 + F4, com F2 como executor |
| Q8 | Canal do time = **tela "Canal do time" na interface React** (no estilo Slack, com aprovação por botão). Adaptador `slack-bolt` só se houver `SLACK_BOT_TOKEN` no `.env`; hoje não há |
| Q10 | Alçada **acumulada por pedido**: soma de **todas** as ações com dinheiro já executadas no pedido, aprovadas ou não, no mesmo grupo de limite (reembolso ≤ R$ 100; reenvio + reimpressão + troca ≤ R$ 200). Uma aprovação cobre só a ação aprovada (revisão do `revisor`, HG-22) |
| Q11 | Fora do escopo do MVP: a demo roda às 08h |
| Q15 | Suspeita = existe ao menos um sinal **forte** (`HASH_REPETIDO`, `CAPTURA_ANTES_DA_ENTREGA`, `EDITOR_DE_IMAGEM`) **e** custo de aceitar o falso (45% do pedido) > custo de sinalizar (R$ 6). Sinais de contexto não tornam o caso suspeito sozinhos: `SEM_EXIF` (EC-15), `REENVIOS_ANTERIORES` (EC-19: registrado sempre que houver reenvio, contando só `tipo == "reenvio"`) e `PERSONALIZACAO_DIVERGENTE` (EC-18: o agente pede nova foto antes de decidir; se a categoria é `erro_personalizacao`, a divergência confirma a reclamação) |
| Q20 | Ação com dinheiro sem pedido identificado → `ESCALAR`, nunca executar (AGENTS.md, regra de dados 4) |
| Q21 | O motor é puro e confia na aprovação que recebe; quem valida o `aprovacao_id` (existe, está aprovada, decidida por supervisor diferente do solicitante, mesma ação, mesmo pedido, valor ≤ aprovado) é o agente (W4) antes de chamar `decidir` |
| Q9 | Vigia: alerta de SLA 10 min antes do vencimento (e para o já vencido); lembrete de aprovação parada a cada 2 h, dentro das 24 h de `reclamacao_suspeita.prazo_decisao_horas`, ao supervisor do turno e nunca ao autor; o cliente com aprovação parada recebe "seu caso segue em análise" |
| Q22 | Incidente (HG-17): **um por (tipo de padrão, dia)**, compartilhado entre o fluxo do caso e a rota do analista; abre quando o padrão afeta 3 ou mais pedidos; cliente já avisado sobre o mesmo incidente não é avisado de novo; o aviso descreve o que foi identificado e o próximo passo, **sem prometer ação ainda não executada** (ex.: estorno que depende de aprovação) |
| Q23 | Contato repetido (HG-16): não repetir só ação **sem dinheiro** já feita com o mesmo motivo (ex.: chamado aberto com a transportadora); ação com dinheiro sempre passa pela política, somando o que já foi executado no pedido (HG-22) |
| Q2 | 7º dia após a entrega está dentro; 8º está fora |
| LLM | Sem `ANTHROPIC_API_KEY` no `.env`: o leitor de mensagens é determinístico (regex e palavras-chave). O SDK `anthropic` entra depois, atrás da mesma interface, só se a chave existir |

## Comandos

```bash
uv sync                                   # backend
uv run pytest -q                          # testes (pythonpath = src)
uv run ruff check . && uv run ruff format --check .
uv run python -m atendimento.dados.carga  # gera var/atendimento.db a partir de docs/ (somente leitura)
uv run uvicorn atendimento.api.app:app --port 8000
pnpm --dir web install && pnpm --dir web dev   # interface em http://localhost:5173 (proxy /api → :8000)
pnpm --dir web test && pnpm --dir web lint
```

## Estrutura

```
src/atendimento/contratos.py      # fronteira entre módulos (só o maestro altera)
src/atendimento/dados/            # W1: CSV → SQLite, repositórios por ID
src/atendimento/ferramentas/      # W1: ferramentas de ferramentas.csv com efeito + log de ações
src/atendimento/politicas/        # W2: motor de políticas (puro, sem I/O)
src/atendimento/verificacao/      # W3: verificador de evidência (puro, sem I/O)
src/atendimento/agente/           # W4: leitor de mensagem + orquestração do caso + aprovações
src/atendimento/api/              # W4: FastAPI + SSE
web/                              # W5: React + Vite + TS
tests/                            # pytest; fixtures mínimas em tests/fixtures/
var/                              # banco gerado (ignorado)
```

## API (contrato entre W4 e W5)

Prefixo `/api`. JSON. Todos os textos ao cliente e ao time já vêm **com CPF, cartão e telefone mascarados**.

| Método e rota | Retorno |
| --- | --- |
| `GET /api/fila` | `[{conversation_id, canal, marca, assunto, order_id, data_abertura, prioridade, estado}]`, `estado` ∈ `aberta, resolvida, aguardando_aprovacao, suspeita, escalada` |
| `POST /api/fila/processar` | processa todas as conversas `aberta`; devolve o placar |
| `POST /api/conversas/{id}/processar` | processa uma; devolve o caso |
| `GET /api/conversas/{id}` | `{conversa, mensagens[{autor, timestamp, texto}], pedido, anexos, veredicto, decisao, acoes[], resposta_ao_cliente}` |
| `GET /api/acoes` | log das ações do agente: `RegistroAcao[]` |
| `GET /api/canal` | mensagens do canal do time: `[{id, tipo: aviso|aprovacao|suspeita|escalacao, para, texto, conversation_id, aprovacao_id?, estado?}]` |
| `POST /api/aprovacoes/{id}/aprovar` | body `{supervisor_id, comentario?}`; executa a ação aprovada; recusa se o supervisor for quem pediu |
| `POST /api/aprovacoes/{id}/rejeitar` | body `{supervisor_id, justificativa}` |
| `GET /api/placar` | `{resolvidas_sozinho, aguardando_aprovacao, suspeitas, escaladas, valor_executado_rs, custo_evitado_rs}` |
| `GET /api/eventos` | SSE: `{tipo, payload}` a cada ação, aprovação ou mensagem no canal |

## Estilo de código

Python 3.12+, funções puras onde der, `dataclasses` de `contratos.py` nas fronteiras, nomes em português como nos dados. Teste com o ID do cenário:

```python
def test_EC_01_reembolso_acima_de_100_pede_aprovacao():
    decisao = decidir(
        AcaoProposta(
            ferramenta="reembolsar",
            papel=Papel.ATENDENTE,
            executado_por="agente",
            order_id="GBH1",
            valor_rs=150.0,
        ),
        acoes_anteriores=[],
        politicas=POLITICAS,
    )
    assert decisao.resultado is Resultado.PEDIR_APROVACAO
```

## Testes

TDD (Red-Green-Refactor) para regras de negócio. Fixtures pequenas em `tests/fixtures/`. "Agora" fixo em `contratos.AGORA`. Testes de integração (`-m integracao`) podem ler `docs/`. E2E: Playwright na interface, evidências em `.scratch/e2e/`.

## Limites

- **Sempre:** teste com ID do cenário; `uv run pytest -q` e `ruff` verdes antes de reportar; números com origem em `docs/`; mascarar dado pessoal.
- **Perguntar ao maestro:** mudar `contratos.py`, `pyproject.toml`, o contrato da API ou arquivo de outro worker.
- **Nunca:** editar `docs/`; marcar `"passes"` em `feature_list.json` (só o `revisor`); lógica de negócio no React; afrouxar ou pular teste.

## Critérios de sucesso do MVP

1. `POST /api/fila/processar` trata as 65 conversas: cada uma termina com ação registrada, pedido de aprovação, suspeita ou escalação (HP-09, N1).
2. Zero ações com dinheiro acima da alçada sem aprovação, inclusive somando ações anteriores do pedido (EC-01, EC-02, HG-05, HG-22).
3. A reação adversa da fila (AT116568) gera orientação de suspensão e pedido de cosmetovigilância (HG-06).
4. Avaria com sinal verificável vira suspeita para o supervisor, com resposta neutra ao cliente (EC-16, EC-17, EC-18, HG-07, HG-08).
5. Supervisor aprova na tela "Canal do time" e a ação aparece no console (HP-10); autoaprovação é recusada (HG-03).
6. Jornada E2E gravada em `.scratch/e2e/`.
