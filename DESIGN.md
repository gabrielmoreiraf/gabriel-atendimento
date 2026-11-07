# DESIGN.md — Demo do agente de atendimento

Fonte única dos valores: `tokens.css` (raiz), importado por `web/src/index.css`.

## Contexto de uso

Banca de hackathon olhando um projetor, a 3–6 m da tela, em sala iluminada. A tela precisa provar em segundos que o agente **age** (anti-requisito N4): não é painel de métricas. Modo *Operate*: legibilidade e leitura rápida acima de enfeite.

## Direção

- **Tema claro por padrão** (projetor em sala clara lava fundos escuros); escuro disponível por `prefers-color-scheme` ou `data-theme="dark"`.
- **Tipografia:** IBM Plex Sans no texto, IBM Plex Mono só para dado de sistema (IDs, valores em R$, referências, horários). Corpo 18px; nada abaixo de 13px.
- **Cor com significado:** um azul-tinta de marca para ações e foco. Os cinco estados da conversa têm cor própria e **sempre** aparecem com o rótulo em texto (nunca só cor):
  `aberta` (neutro) · `resolvida` (verde) · `aguardando_aprovacao` (âmbar) · `aguardando_cliente` (azul-petróleo: pedimos foto, não conta como resolvida) · `suspeita` (vermelho) · `escalada` (violeta).
- **Canal do time:** painel escuro próprio, inspirado em ferramentas de chat de equipe, com marca da demo ("Canal #atendimento-ops"). Sem logo ou cores de terceiros.

## Layout (≥1280px)

```
┌ Placar (barra no topo, 6 números) ───────────────── [Processar fila] ┐
├ Fila (lista) ─┬ Caso aberto (chat · evidência · decisão · resposta) ─┤
│               ├ Console dos sistemas (log ao vivo, tabela mono) ─────┤
└───────────────┴──────────────────────── Canal do time (coluna direita)┘
```

Abaixo da primeira tela: **Verificação de evidência** (frente da PoC, em destaque) e **Agente analista** (padrões de causa comum → incidente). O vigia roda pelo canal do time, com o controle "Avançar o relógio para 08:20": o front só passa o horário.

Abaixo de 1100px as colunas empilham.

## Regras

- Nenhuma regra de negócio no front (ADR-001): a UI só exibe o que a API devolve e dispara ações.
- Dados pessoais chegam mascarados da API; a UI não desfaz máscara.
- Movimento: só a entrada de uma nova linha no console e no canal (realce que esmaece, `--dur-med`). Respeita `prefers-reduced-motion`.
- Foco de teclado visível (`--color-focus`), alvos de clique ≥ 40px.
- `data-testid` estáveis para o E2E: `placar`, `btn-processar`, `fila-item`, `console-acao`, `canal-msg`, `btn-aprovar`, `btn-rejeitar`, `replay-item`, `btn-replay`, `sinal-evidencia`, `padrao-item`, `btn-tratar-padrao`, `resultado-padrao`, `btn-rodar-vigia`, `btn-vigia-0820`.
