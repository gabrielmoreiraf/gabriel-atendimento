# Jornada E2E (camada 5)

`jornada.mjs` percorre a demo no navegador com Playwright (`playwright-skill`) e grava as evidências em `.scratch/e2e/`.

## O que a jornada faz

1. Abre a página e lê o placar (`data-testid="placar"`).
2. Clica em **Processar fila** (`btn-processar`) e espera as ações aparecerem no console (`console-acao`).
3. Abre `AT116568` (reação adversa, única na fila) e confere que ficou `escalada`, com decisão da política.
4. Abre o primeiro caso em `suspeita`: precisa listar sinais de evidência, e a resposta ao cliente não pode usar "fraude", "golpe", "mentira", "falso/falsa" nem "suspeita" (HG-07). A `fila_aberta.csv` das 08h não tem anexos, então o esperado é zero suspeitas. Nesse caso a jornada registra "não se aplica" sem acusar falha, desde que o placar também mostre zero.
5. No canal do time (`canal-msg`), pega um pedido de aprovação pendente e:
   - tenta a **autoaprovação** com o solicitante: pela tela, quando o solicitante é supervisor, ou direto em `POST /api/aprovacoes/{id}/aprovar`, quando não é. Espera a recusa (HG-03);
   - aprova com um supervisor **diferente** do solicitante (`btn-aprovar`).
6. Confere que a ação aprovada aparece no console com o aprovador (HP-10).
7. Os pedidos de foto ficam em `aguardando_cliente`, e o número na tela bate com a API. Abre um deles e confere que a resposta pede a foto.
8. **Verificação de evidência por replay** (`replay-item`, `btn-replay`, `sinal-evidencia`): processa `AT104936` e confere que aparece um sinal forte (hash repetido, captura antes da entrega ou editor de imagem) e que a resposta ao cliente é neutra.
9. **Agente analista**: trata o padrão `cobranca_em_dobro` e confere o incidente `INC-` no console.
10. **Vigia**: às 10:00, lembra o supervisor da aprovação que ficou pendente (HG-21).
11. Confere que a página não teve erro de JavaScript.

Antes de processar a fila (passo 1b), o vigia roda às 08:20 (`btn-vigia-0820` ou `POST /api/vigia/rodar`). Os avisos de SLA aparecem no canal, e uma segunda rodada não repete nenhum aviso (HG-20).

Seletores tolerantes: quando a tela ainda não tem o elemento (por exemplo, o botão do analista), a jornada usa a rota da API e registra o item como `N/D` (não disponível) em `relatorio.json`. Item `N/D` não conta como falha.

O solicitante vem de `GET /api/canal`, nos campos `solicitado_por` ou `executado_por`. Se a API não mandar nenhum dos dois, a jornada procura no texto da mensagem um id que não seja o do campo `para`. Sem nada disso, o solicitante é `agente`, o executor do backend (`agente/caso.py`, `EXECUTOR`). Para forçar outro valor, use `E2E_SOLICITANTE`, por exemplo `supervisor_02` no modo mock do front (`E2E_URL="http://localhost:5173/?mock"`).

## Como rodar

Pré-requisitos: `uv sync`, `pnpm --dir web install`, `ffmpeg` (opcional, gera o `.mp4`).

```sh
# terminal 1: backend (FastAPI)
uv run uvicorn atendimento.api.app:app --port 8000

# terminal 2: front (Vite em http://localhost:5173, proxy /api -> :8000)
pnpm --dir web dev

# terminal 3: jornada
SKILL_DIR=~/.claude/skills/playwright-skill   # pasta da playwright-skill
node "$SKILL_DIR/run.js" e2e/jornada.mjs
```

Desligue os dois servidores (Ctrl+C) quando a jornada terminar.

### Em portas próprias, sem mexer na demo (:8010 e :5199)

O proxy de `web/vite.config.ts` aponta fixo para `:8000`. `e2e/vite.e2e.config.mjs` reaproveita essa config e troca só o alvo (`E2E_API`, padrão `http://localhost:8010`). Use um banco à parte para não misturar estado com o backend da demo:

```sh
ATENDIMENTO_DB=/tmp/e2e.db uv run uvicorn atendimento.api.app:app --port 8010
pnpm --dir web exec vite --config ../e2e/vite.e2e.config.mjs --port 5199 --strictPort
E2E_URL=http://localhost:5199 node "$SKILL_DIR/run.js" e2e/jornada.mjs
```

A jornada processa a fila e aprova um pedido. Rode sempre contra um backend com estado zerado, porque o passo "placar mudou" espera a fila ainda aberta.

Variáveis opcionais:

| Variável | Padrão | Uso |
| --- | --- | --- |
| `E2E_URL` | `http://localhost:5173` | endereço do front |
| `E2E_SAIDA` | `.scratch/e2e` | onde gravar as evidências |
| `PW_HEADLESS` | `true` | `false` abre o navegador visível |
| `SLOW_MO` | `0` | atraso entre ações (ms), útil para gravar a demo |
| `E2E_TIMEOUT_PROCESSAR_MS` | `180000` | limite para processar a fila |
| `E2E_REPLAY` | `AT104936` | conversa do histórico usada no replay |
| `E2E_PADRAO` | `cobranca_em_dobro` | padrão tratado pelo agente analista |
| `E2E_VIGIA_AGORA` / `E2E_VIGIA_LEMBRETE` | `2026-11-02T08:20:00` / `T10:00:00` | horários das rodadas do vigia |

## Saídas em `.scratch/e2e/`

- `NN-<passo>.png`: screenshot de página inteira de cada passo;
- `jornada.webm` e `jornada.mp4`: vídeo da jornada;
- `relatorio.json`: cada verificação com `ok` e detalhe. O processo sai com código 1 se alguma falhar.
