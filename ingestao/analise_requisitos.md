# Análise de requisitos — REQUISITOS.md v2

Camada 1 · skill `requirements-analysis` (awesome-qa-skills) · 2026-11-07
Entrada: `REQUISITOS.md` v2 (54 cenários), `ingestao/desafio/enunciado.md`, `docs/politicas.csv`, `docs/ferramentas.csv`, `docs/equipe_atendimento.csv`.
Números novos: seção M11 de `ingestao/baseline_metricas.md` (reproduzível).

## 1. Requirement Understanding

**Escopo:** agente "colega de trabalho" que trata a fila de atendimento Gocase/GoBeauté (WhatsApp, e-mail, Reclame Aqui). Ele age nos sistemas dentro da alçada, verifica a reclamação antes de agir, escala para a pessoa certa e conversa com o time pelo canal do time. A PoC prova uma frente; o plano cobre as cinco (F1–F5).

**Objetivo de negócio:** reduzir custo e tempo por contato e o recontato, com zero violação de política e alçada.

**Fatos confirmados** (estão nos arquivos):
- limites por papel, prazos por categoria, regras de suspeita, cosmetovigilância e dados pessoais (`politicas.csv`);
- ferramentas e papéis permitidos (`ferramentas.csv`); `registrar_cosmetovigilancia`, `aprovar_acao` e `decidir_suspeita` são exclusivas do supervisor;
- turnos dos supervisores (`equipe_atendimento.turno`);
- custo do erro na suspeita, nos dois sentidos (`parametros.md`);
- o README declara **"Sem gabarito"**: as respostas e os problemas plantados não foram distribuídos.

**Suposições atuais** (marcadas para confirmar):
- A1. O agente atua no papel `atendente`. O agente analista é um segundo agente (HG-19).
- A2. O "ambiente" de tiques, `ver_anexos` e pedidos de colaboradores (`parametros.md`) **não está no repositório**. Vamos simulá-lo a partir dos CSVs.
- A3. "Até 7 dias do recebimento" é inclusivo (Q2).
- A4. Frente da PoC = F3 + F4; canal = Slack (Q1, Q8).
- A5. Em EC-19, o critério "`n_trocas_12m` acima da mediana" **foi inventado na v2** e não tem fonte. Deve ser removido.

## 2. Gaps and Ambiguities

Ordenadas por risco.

| # | Lacuna | Evidência | Cenários afetados |
| --- | --- | --- | --- |
| G1 | **Alçada e repetição medidas por chamada, não por pedido.** A política fala em "1 troca por pedido" e em limite em R$ por ação, mas não diz se o limite é acumulado no pedido. No histórico, a mesma ação se repete no mesmo pedido em conversas diferentes. | M11: 108 de 418 pedidos com 2+ reenvios; **7 de 89 com 2+ trocas, contra a regra de 1 por pedido**; 64 casos em que cada execução cabe na alçada, mas a soma passa do limite sem aprovação, todos em conversas diferentes | EC-01, EC-02, EC-07, HG-05, HG-12, HG-16 |
| G2 | **Horário de operação do agente indefinido.** A política diz que fora das 8h–20h "só o bot responde". O agente de IA é o bot ou um atendente? Pode executar reenvio às 23h? | M11: 869 de 2.984 conversas (29,1%) abertas fora do horário humano | HP-01, EC-06, EC-22 |
| G3 | **Arrependimento com pedido em trânsito.** A política cobre "antes da separação" (cancelar) e "depois do recebimento" (reembolso em 7 dias). O período entre um e outro não tem regra. | `politicas.categorias.arrependimento_cancelamento.regra` | sem cenário |
| G4 | **Reembolsos acima de R$ 100 sem caminho no fluxo principal.** HP-05 só cobre duplicidade até R$ 100; arrependimento depois do recebimento e reembolso por atraso não têm cenário com aprovação. | M11: das 12 cobranças em dobro sem estorno, 6 passam de R$ 100 | HP-05, HP-11 |
| G5 | **Quando sinalizar suspeita não é quantitativo.** Os cenários listam sinais (hash, EXIF, editor), mas não há regra de decisão. Os custos de `parametros.md` permitem uma regra de valor esperado (sinalizar custa R$ 6; aceitar uma falsa custa 45% do pedido; negar uma verdadeira custa ½ LTV + 30% × R$ 42). | `parametros.md` "Reclamações que não procedem" | HP-04, EC-15..19, HG-07 |
| G6 | **Resposta pública no Reclame Aqui sem requisito.** A política exige resposta pública em até 48 h, e o canal não tem bot. Nenhum cenário trata conteúdo público (dado pessoal exposto, tom, promessa). | 24 conversas na fila; 50,4% do custo (M1) | HP-01 |
| G7 | **Consentimento ignorado no aviso proativo.** `notificar_clientes` não considera `aceita_comunicacao_whatsapp` / `aceita_comunicacao_email`. Nenhuma política cita consentimento, mas a coluna existe. | M11: 358 clientes sem consentimento para WhatsApp e 574 para e-mail | HG-17 |
| G8 | **Categorias sem cenário:** Dúvida, Promoção/cupom, Elogio, Outros, Reclamação produto e alteração de endereço antes da separação (só o caso negado existe). | M2: 611 conversas (20,5%) nessas tags | — |
| G9 | **"% do produto utilizado" não é verificável nos dados.** A troca de fragrância exige ≤ 20%, mas nenhuma coluna mede isso. | `politicas.troca_fragrancia.max_produto_usado_pct` | EC-07 |
| G10 | **Critério sem fonte** em EC-19 ("acima da mediana"). | A5 | EC-19 |
| G11 | **Faltam metas de sucesso do produto.** O objetivo diz "reduzir custo e tempo" sem número; só o HG-18 tem meta (0 violações). | — | HG-18 |

## 3. Risk Assessment

| Risco | Impacto | Probabilidade | Prioridade | Mitigação |
| --- | --- | --- | --- | --- |
| R1. Agente repete reenvio, troca ou reembolso no mesmo pedido a cada recontato (G1) | perda financeira direta; viola "1 troca por pedido" | **alta**: 32,9% das conversas são recontato (M4) | **P0** | alçada acumulada por pedido + checagem de ações anteriores (HG-22) |
| R2. Ação com dinheiro fora do horário, sem humano para aprovar ou intervir (G2) | aprovação impossível; erro sem supervisão | alta (29,1% fora do horário) | **P0** | decidir Q11; até lá, só ações sem dinheiro fora do horário |
| R3. Falso negativo ou positivo na suspeita (G5) | ½ LTV + RA ou 45% do pedido | média | **P0** (frente da PoC) | regra de valor esperado no SPEC; sinais só por fatos verificáveis |
| R4. Resposta pública no RA com dado pessoal ou promessa indevida (G6) | reputação + LGPD | média | **P1** | HP-12 + filtro de PII antes de publicar |
| R5. Aviso proativo para cliente sem consentimento (G7) | LGPD | média | **P1** | HG-23 |
| R6. Arrependimento em trânsito tratado de improviso (G3) | inconsistência; reclamação | baixa | **P2** | EC-25: escalar até a regra existir |
| R7. Avaliação sem gabarito (README) | não dá para provar a acurácia da suspeita | certa | **P1** | conjunto de casos rotulados a partir dos sinais plantados; métricas de conformidade, não de acurácia |

## 4. Testability Impact

- **Não testáveis como estão:** HG-14 (limiar de confiança indefinido), HG-20/HG-21 (tempos indefinidos), EC-07 (% de uso), EC-19 (critério inventado) e G5 (sem regra de decisão).
- **Dependem de simulador que não existe** (A2): EC-11 (tiques), HP-10/HG-20/HG-21 (canal do time), `ver_anexos` nas conversas novas. É preciso definir a interface das ferramentas e construir mocks no `/spec`.
- **Problema de oráculo:** sem gabarito, a "taxa de acerto" do HG-18 só pode usar `tag_agente` (manual, com ruído) e a conformidade com a política. A detecção de suspeita precisa de um conjunto de teste rotulado por nós, com critério documentado.
- **Não determinismo:** comparar `descricao_visual` com o pedido envolve texto livre. A decisão precisa ficar em regra determinística; o modelo só extrai os campos (alinhado ao HG-01).
- **Testáveis já:** limites em R$ (EC-01/02), prazos (EC-03..06), papéis (HG-02..04), PII (HG-11), idempotência (HG-12), contra fixtures pequenas.

## 5. Open Questions

| # | Pergunta (para quem) | Por que importa |
| --- | --- | --- |
| Q10 | O limite do atendente (R$ 100 / R$ 200) vale **por ação ou acumulado por pedido**? Um segundo reenvio do mesmo pedido em outra conversa conta junto? (negócio) | Define o HG-22 e fecha o caminho de fracionamento (R1) |
| Q11 | Fora das 8h–20h o agente de IA pode **executar ações** ou só responder como o bot? Se pode, quais ações e até que valor? (negócio) | 29,1% das conversas; muda HP-01, EC-06 e EC-22 |
| Q12 | Arrependimento com pedido **separado e ainda não entregue**: cancelar, recusar a entrega ou esperar o recebimento? (negócio/jurídico) | Regra inexistente (G3) |
| Q13 | O aviso proativo (`notificar_clientes`) deve respeitar `aceita_comunicacao_*`? Aviso de atraso conta como comunicação transacional? (jurídico) | LGPD (G7) |
| Q14 | Como verificar "no máximo 20% do produto utilizado": foto, declaração do cliente ou peso? (negócio) | Torna o EC-07 testável |
| Q15 | Qual regra decide sinalizar suspeita: valor esperado com os custos de `parametros.md`, ou número mínimo de sinais verificáveis? (produto) | Núcleo da PoC F3 (G5, R3) |
| Q16 | Quais metas de sucesso a PoC deve bater (ex.: % resolvido sem humano, SLA cumprido, violações = 0, escalações corretas)? (produto) | Torna o objetivo mensurável (G11) |

## 6. Recommended Next Steps

1. Atualizar `REQUISITOS.md` para v3:
   - novos cenários: HP-12 (resposta pública RA), HP-13 (categorias simples), EC-23 (arrependimento > R$ 100), EC-24 (duplicidade > R$ 100), EC-25 (arrependimento em trânsito), HG-22 (segunda ação de dinheiro no mesmo pedido), HG-23 (consentimento);
   - corrigir o EC-19 (remover "mediana");
   - adicionar Q10–Q16.
2. Regenerar `feature_list.json` e submeter a v3 ao subagente `revisor`.
3. Rodar `test-strategy` (camada 1) para fixar os níveis de teste, o oráculo sem gabarito e a interface do simulador.
4. Com Q1, Q8, Q10, Q11 e Q15 respondidas, seguir para `/spec` (camada 4).
