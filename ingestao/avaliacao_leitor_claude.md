# Avaliação do leitor: regras × Claude (HG-18)

- **Modelo:** `claude-opus-5-5` (padrão da skill `claude-api`, `effort: low`, saída estruturada)
- **Amostra:** 300 conversas do histórico com mensagem do cliente, estratificada pela
  `tag_agente` (semente 42), sempre com as conversas de cosmetovigilância e de
  instrução embutida
- **Data da medição:** 2026-11-07
- **Gerado por:** `uv run python -m atendimento.avaliacao --leitor claude --amostra 300`

## Acerto de categoria contra a tag humana

A categoria de cada leitor vira tag por `politicas.categorias.<categoria>.tag_equivalente`
(mesmo critério de `ingestao/avaliacao_offline.md`, seção 3).

| leitor | acertos | acerto |
| --- | --- | --- |
| regras | 161 | 53.7% |
| Claude (com a rede de segurança) | 186 | 62.0% |

| tag humana | conversas | regras | Claude |
| --- | --- | --- | --- |
| Rastreio | 63 | 41 (65.1%) | 49 (77.8%) |
| Atraso | 49 | 36 (73.5%) | 40 (81.6%) |
| Outros | 24 | 3 (12.5%) | 2 (8.3%) |
| Avaria | 24 | 17 (70.8%) | 19 (79.2%) |
| Dúvida | 23 | 4 (17.4%) | 9 (39.1%) |
| Troca | 23 | 7 (30.4%) | 6 (26.1%) |
| Reclamação produto | 19 | 9 (47.4%) | 9 (47.4%) |
| Produto faltando | 18 | 15 (83.3%) | 18 (100.0%) |
| Cancelamento | 16 | 6 (37.5%) | 9 (56.2%) |
| Financeiro | 14 | 4 (28.6%) | 6 (42.9%) |
| Endereço | 12 | 5 (41.7%) | 5 (41.7%) |
| Promoção | 11 | 11 (100.0%) | 11 (100.0%) |
| Elogio | 4 | 3 (75.0%) | 3 (75.0%) |

O Claude mudou a categoria das regras em 45 das 300 conversas.

## Segurança

| medida | total na amostra | regras | Claude (com a rede) |
| --- | --- | --- | --- |
| cosmetovigilância vista como sensível (HG-06) | 27 | 27 | 27 |
| instrução embutida sinalizada (HG-09) | 3 | 3 | 3 |

## Custo e falhas

- Chamadas pagas nesta execução: 300 (as demais vieram do cache em `var/`).
- Custo estimado desta execução: US$ 2.37 (tokens de `usage` × US$ 4/MTok de entrada e
  US$ 20/MTok de saída, tabela da skill `claude-api` para `claude-opus-5-5`).
- Quedas para o leitor por regras (HG-13): 0
  (nenhuma).
