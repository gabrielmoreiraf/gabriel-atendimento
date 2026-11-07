# Linha de base: métricas da dor de negócio

Gerado por `ingestao/baseline_metricas.py`. Agora fixo: 2026-11-02 08:00.

## M1. Volume e custo por canal (`historico_conversas.canal` × `politicas.custo_por_conversa_rs`)

| Canal | Conversas | Custo unitário (R$) | Custo na amostra (R$) |
| --- | ---: | ---: | ---: |
| whatsapp | 1963 | 4.80 | 9,422.40 |
| email | 675 | 7.20 | 4,860.00 |
| reclame_aqui | 346 | 42.00 | 14,532.00 |
| **Total** | **2984** | | **28,814.40** |

Amostra de 1 em cada 4 clientes (`parametros.md`).

## M2. Motivos de contato (`historico_conversas.tag_agente`)

| Tag | Conversas | % |
| --- | ---: | ---: |
| Rastreio | 616 | 20.6% |
| Atraso | 466 | 15.6% |
| (sem tag: só bot) | 330 | 11.1% |
| Avaria | 213 | 7.1% |
| Dúvida | 187 | 6.3% |
| Produto faltando | 178 | 6.0% |
| Outros | 178 | 6.0% |
| Troca | 158 | 5.3% |
| Cancelamento | 156 | 5.2% |
| Financeiro | 138 | 4.6% |
| Endereço | 118 | 4.0% |
| Promoção | 105 | 3.5% |
| Reclamação produto | 104 | 3.5% |
| Elogio | 37 | 1.2% |

## M3. Status e esforço (`historico_conversas.status`, `tempo_por_conversa`)

- status `resolvido`: 2237 (75.0%)
- status `sem_resposta_cliente`: 404 (13.5%)
- status `pendente`: 343 (11.5%)
- minutos trabalhados: média 12.2, total 32,289 min em 2654 conversas
- sistemas acessados por conversa: média 1.83, máximo 4
- sistemas distintos no log de ações (`acoes_executadas_sistemas.sistema`): 11

## M4. Contatos repetidos (`historico_conversas` por `customer_id` + `order_id`)

- pares cliente+pedido com 2+ conversas: 453
- conversas nesses pares: 982 (32.9% do histórico)
- conversas da fila sobre pedido que já teve conversa no histórico: 13 de 65

## M5. Fila de agora (`fila_aberta`, SLA de `politicas.sla_primeira_resposta`)

| Canal | Na fila | Sem 1ª resposta humana | Já fora do SLA |
| --- | ---: | ---: | ---: |
| whatsapp | 19 | 18 | 0 |
| email | 22 | 22 | 1 |
| reclame_aqui | 24 | 19 | 0 |

## M6. Evidência das reclamações (`anexos_conversas` × `pedidos.data_entrega`)

- anexos: 382; sem EXIF de captura: 212 (55.5%)
- anexos com mesmo `hash_perceptual` em pedidos diferentes: 17 (8 hashes)
- anexos com EXIF de captura anterior à entrega do pedido: 11
- anexos com `exif_software` preenchido (passaram por editor): 10

## M7. Cobrança em dobro (`pagamentos_gateway` por `order_id`)

- pedidos com 2+ transações capturadas/pagas/estornadas: 81
- pedidos com 2+ transações capturadas/pagas ainda sem estorno: 12

## M8. Alçadas no histórico (`acoes_executadas_sistemas` × `politicas.limites_por_papel`)

- ações com dinheiro acima do limite do atendente: 132; sem `aprovado_por`: 0
- ações aprovadas pelo próprio executor: 0
- trocas/reenvios/novas produções: 667, custo total R$ 36,195.89 (`trocas_reenvios.custo_total`)

## M9. Satisfação (`avaliacoes_csat`, `reclame_aqui`)

- pesquisas enviadas: 1975; respondidas: 619 (31.3%); nota média 3.82 de 5
- notas 1-2: 62 (10.0%)
- reclamações no Reclame Aqui: 370; `resolvido`: {'': 184, 'sim': 115, 'não': 71}

## M10. Sinais nos textos dos clientes (`historico_mensagens`, autor = cliente)

- possível reação adversa: 27 mensagens em 27 conversas (1 na fila: AT116568)
  - `AT104663`: "Olá, equipe Rituária, tudo bem? Comecei a tomar a biotina e tive dor de barriga forte e manchas vermelhas na pele. Tô preocupado. Pedido GBH"
  - `AT106224`: "[Produto causou alergia] O perfume Neroli me deu alergia no pescoço, ficou vermelho e coçando. O que eu faço? Pedido GBH######."
  - `AT106234`: "A paleta de sombras deu alergia nos meus olhos, ficaram inchados e lacrimejando. Tô preocupado. Outra coisa: se não chegar até terça quero c"
- instrução embutida dirigida ao agente (prompt injection): 3 mensagens em 3 conversas (0 na fila: -)
  - conversas: AT105778, AT108856, AT116445 (texto omitido de propósito)
- dado pessoal (CPF, cartão, telefone): 244 mensagens em 244 conversas (4 na fila: AT116507, AT116560, AT116669, AT116705)
- mais de um pedido na mesma mensagem: 107 mensagens em 107 conversas (2 na fila: AT116597, AT116697)
- registros de cosmetovigilância no log (`acoes_executadas_sistemas`): 27

## M11. Lacunas de requisito (`acoes_executadas_sistemas`, `pagamentos_gateway`, `clientes`, `historico_conversas`)

- `reenviar_produto`: 108 de 418 pedidos receberam a ação 2+ vezes
- `trocar_produto`: 7 de 89 pedidos receberam a ação 2+ vezes
- `reembolsar`: 9 de 113 pedidos receberam a ação 2+ vezes
- `reimprimir_personalizacao`: 4 de 24 pedidos receberam a ação 2+ vezes
- pedido+ação repetidos em que cada execução cabe na alçada mas a soma passa do limite, sem aprovação: 64 (em conversas diferentes: 64)
- cobranças em dobro sem estorno: 6 com valor ≤ R$ 100, 6 acima (exigem aprovação)
- clientes sem consentimento: WhatsApp 358, e-mail 574 de 2867
- conversas abertas fora do horário humano (antes das 08h ou a partir das 20h): 869 de 2984 (29.1%)

## M12. Cortes temporais e percentuais derivados (revisão do REQUISITOS.md v3)

- pedidos criados em ou depois de agora (`pedidos.data_hora_pedido` ≥ 2026-11-02 08:00:00): 273; pelo campo só de data (`data_pedido` > 2026-11-02): 243 (diferença de 30 pedidos de 02/11 depois das 08h)
- conversas da fila sem `order_id`: 6
- Reclame Aqui: 11.6% das conversas e 50.4% do custo
- Rastreio + Atraso: 36.3% das conversas

