# DESIGN.md — Gabriel, o colega de atendimento

Fonte única dos valores: `tokens.css` (raiz), importado por `web/src/index.css`. Base visual: **brandbook do Gogroup** (`ingestao/` não guarda o PDF; ele fica com o autor).

## Identidade (brandbook Gogroup)

- **Azul `#2659a5` é a cor protagonista**; **limão `#d7d900`** entra em blocos de cor (moldura, destaques, etiquetas). Apoio: azul-claro `#3dbfef`, rosa `#e61782`, amarelo `#f8ae13`, laranja `#e5381a`.
- **Contraste do manual:** nunca branco sobre limão ou amarelo; não colocar laranja, vermelho e rosa lado a lado.
- **Tipografia:** Poppins (bold para títulos, regular para texto); IBM Plex Mono só para dado de sistema (IDs, valores, horários, referências).
- **Logotipo do Gogroup não é usado** (sem arquivo oficial; o manual proíbe recriar ou distorcer). O nome aparece em texto, grafado "Gogroup".
- **Mascote do Gabriel:** balão de conversa azul com olhos e sorriso limão e um fio saindo da cauda (`web/src/landing/Mascote.tsx`).

## Superfícies

| Rota | Modo | O que é |
| --- | --- | --- |
| `/` | Persuade | Landing: hero azul com moldura limão, mascote e balões de chat; problema e resultados como listas tipográficas; cinco passos; Slack; visão 360°; chamada final |
| `/app` | Operate | A ferramenta: abas Operação, Evidência, Analista e Mapa 360° |

## Ferramenta (`/app`)

- Barra superior com o PillNav (React Bits, `web/src/vendor/reactbits/`), relógio da demo e Reiniciar.
- Operação: placar em cartões (ponto de cor + rótulo) com **Processar fila**; fila com filtros por estado e sigla do canal; caso + console no centro; **canal do time em azul-marinho** à direita.
- Evidência, Analista e Mapa: mesma moldura (largura máx. 1200px) e o mesmo título de tela.
- Celular: barra inferior Fila · Canal · Evidência · Analista.
- Estados da conversa sempre com rótulo em texto (nunca só cor): aberta, resolvida, aguardando aprovação, aguardando cliente, suspeita, escalada.

## Regras

- Nenhuma regra de negócio no front (ADR-001): a UI só exibe o que a API devolve e dispara ações.
- Dados pessoais chegam mascarados da API; a UI não desfaz máscara.
- Movimento: um momento autoral por superfície (mascote flutuando e piscando na landing; realce de linha nova no console e no canal). Respeita `prefers-reduced-motion`.
- Seleção de texto, cursor, barra de rolagem e anel de foco vêm da paleta. Alvos de clique ≥ 40px (44px no celular).
- Microinterações do MicroKit UI (MIT) no botão "Abrir o Gabriel" e nos cartões dos cinco passos, com aviso de licença junto do código.
- `data-testid` estáveis para o E2E: `placar`, `btn-processar`, `fila-item`, `console-acao`, `canal-msg`, `btn-aprovar`, `btn-rejeitar`, `replay-item`, `btn-replay`, `sinal-evidencia`, `padrao-item`, `btn-tratar-padrao`, `resultado-padrao`, `btn-rodar-vigia`, `btn-vigia-0820`, `btn-reiniciar`, `lp-entrar`.
