# Avaliação offline contra o histórico (HG-18)

Reexecução do motor de políticas (`atendimento.politicas`) e do verificador de evidência (`atendimento.verificacao`) sobre o histórico de `docs/`. Gerado por `uv run python -m atendimento.avaliacao`; não edite à mão.

## 1. Ações com dinheiro: o que o agente teria decidido

**790** ações com dinheiro no histórico. O agente teria decidido diferente do time em
**199** (25,2%). Essas ações somam
**R$ 23.522,81** que o agente não teria executado sozinho.

| ação | ações | com aprovação no histórico | executar | pedir_aprovacao | sinalizar_suspeita | escalar | negar | bloquear | divergem |
|---|---|---|---|---|---|---|---|---|---|
| reembolsar | 123 | 43 | 81 | 3 | 0 | 35 | 4 | 0 | 42 |
| reenviar_produto | 541 | 65 | 407 | 48 | 0 | 66 | 20 | 0 | 134 |
| reimprimir_personalizacao | 29 | 4 | 15 | 0 | 0 | 14 | 0 | 0 | 14 |
| trocar_produto | 97 | 20 | 88 | 0 | 0 | 1 | 8 | 0 | 9 |
| **total** | 790 | 132 | 591 | 51 | 0 | 116 | 32 | 0 | 199 |

### Por que divergem

| motivo | descrição | ações | valor executado |
|---|---|---|---|
| `alcada_acumulada` | Cada ação cabe na alçada, mas a soma no pedido passa do limite (Q10, HG-22) | 51 | R$ 6.592,68 |
| `prazo` | Fora dos dias corridos do recebimento da categoria (EC-03) | 24 | R$ 2.964,87 |
| `antes_do_recebimento` | Ação antes da entrega (ou sem entrega) em categoria com prazo do recebimento: o agente escala para conferir com a logística (EC-25, Q12) | 10 | R$ 831,29 |
| `troca_repetida` | Segunda troca no mesmo pedido (HG-22) | 8 | R$ 815,53 |
| `acao_nao_permitida` | Ferramenta fora de `categorias.<categoria>.acoes_permitidas` para a tag da conversa: o agente escala | 106 | R$ 12.318,44 |

### Ações fora das permitidas, por categoria

A categoria vem da `tag_agente` humana, e parte pode ser tag imprecisa: conversas marcadas
"Rastreio" com reenvio ou reembolso, ações que a política só prevê em `atraso_entrega`. O agente
classifica a conversa de novo antes de decidir, então este número é teto, não previsão.

| categoria (pela tag) | ação executada | ações |
|---|---|---|
| `onde_esta_pedido` | reenviar_produto | 35 |
| `troca_fragrancia` | reenviar_produto | 20 |
| `onde_esta_pedido` | reembolsar | 16 |
| `arrependimento_cancelamento` | reenviar_produto | 11 |
| `avaria_vazamento` | reimprimir_personalizacao | 9 |
| `troca_fragrancia` | reembolsar | 7 |
| `troca_fragrancia` | reimprimir_personalizacao | 5 |
| `arrependimento_cancelamento` | trocar_produto | 1 |
| `alteracao_endereco` | reembolsar | 1 |
| `duvida_produto` | reembolsar | 1 |

### M11: soma acima da alçada sem aprovação (Q10)

**64** pares (pedido, ação) em que a mesma ação se repetiu em conversas diferentes,
cada execução dentro da alçada, nenhuma aprovada, e a soma passou do limite. O motor barra
**64 de 64** antes de o dinheiro sair. Primeira ação barrada em cada caso: `pedir_aprovacao` em 37, `escalar` em 19, `negar` em 8
(`negar` quando a mesma ação também cai fora do prazo ou é a segunda troca; `escalar` quando
veio antes da entrega registrada ou fora das ações permitidas da categoria).

| pedido | ação | conversas | soma executada | limite | 1ª ação barrada | decisão do agente |
|---|---|---|---|---|---|---|
| GBH358290 | reenviar_produto | 2 | R$ 303,62 | R$ 200,00 | AC000400 | escalar |
| GBH360150 | reenviar_produto | 2 | R$ 271,60 | R$ 200,00 | AC000432 | pedir_aprovacao |
| GBH362485 | trocar_produto | 3 | R$ 437,40 | R$ 200,00 | AC000571 | negar |
| GBH363036 | reenviar_produto | 2 | R$ 235,62 | R$ 200,00 | AC000725 | escalar |
| GBH364845 | reenviar_produto | 2 | R$ 211,60 | R$ 200,00 | AC000495 | escalar |
| GBH365587 | reenviar_produto | 2 | R$ 239,40 | R$ 200,00 | AC000297 | negar |
| GBH365649 | reenviar_produto | 2 | R$ 261,62 | R$ 200,00 | AC000938 | escalar |
| GBH367603 | reenviar_produto | 2 | R$ 203,84 | R$ 200,00 | AC000920 | pedir_aprovacao |
| GBH368766 | reenviar_produto | 2 | R$ 297,62 | R$ 200,00 | AC000438 | pedir_aprovacao |
| GBH373049 | reenviar_produto | 2 | R$ 219,80 | R$ 200,00 | AC000551 | negar |
| GBH374021 | reenviar_produto | 4 | R$ 291,24 | R$ 200,00 | AC001144 | pedir_aprovacao |
| GBH376268 | reenviar_produto | 3 | R$ 218,40 | R$ 200,00 | AC001215 | escalar |
| GBH377162 | reenviar_produto | 3 | R$ 209,40 | R$ 200,00 | AC001478 | pedir_aprovacao |
| GBH377832 | reenviar_produto | 2 | R$ 279,62 | R$ 200,00 | AC000702 | pedir_aprovacao |
| GBH384012 | reenviar_produto | 2 | R$ 217,60 | R$ 200,00 | AC001132 | pedir_aprovacao |
| GBH390453 | reenviar_produto | 2 | R$ 219,80 | R$ 200,00 | AC001257 | negar |
| GBH391994 | reembolsar | 3 | R$ 148,23 | R$ 100,00 | AC001020 | pedir_aprovacao |
| GBH393304 | reenviar_produto | 2 | R$ 377,46 | R$ 200,00 | AC001405 | pedir_aprovacao |
| GBH395398 | reembolsar | 2 | R$ 157,60 | R$ 100,00 | AC001102 | pedir_aprovacao |
| GBH398975 | reenviar_produto | 2 | R$ 279,80 | R$ 200,00 | AC001952 | escalar |
| GBH399494 | reenviar_produto | 2 | R$ 246,62 | R$ 200,00 | AC002282 | escalar |
| GBH404751 | reenviar_produto | 2 | R$ 207,46 | R$ 200,00 | AC001814 | negar |
| GBH406386 | reenviar_produto | 2 | R$ 241,62 | R$ 200,00 | AC002670 | pedir_aprovacao |
| GBH409564 | reenviar_produto | 2 | R$ 225,60 | R$ 200,00 | AC002772 | pedir_aprovacao |
| GBH409705 | reenviar_produto | 3 | R$ 479,40 | R$ 200,00 | AC002288 | pedir_aprovacao |
| GBH412238 | reenviar_produto | 2 | R$ 235,62 | R$ 200,00 | AC002962 | escalar |
| GBH415253 | reembolsar | 2 | R$ 173,62 | R$ 100,00 | AC002547 | negar |
| GBH424501 | reenviar_produto | 2 | R$ 211,60 | R$ 200,00 | AC002743 | pedir_aprovacao |
| GBH426539 | reenviar_produto | 2 | R$ 245,60 | R$ 200,00 | AC003578 | escalar |
| GBH433689 | reembolsar | 2 | R$ 111,10 | R$ 100,00 | AC002617 | pedir_aprovacao |
| GBH434974 | trocar_produto | 2 | R$ 305,60 | R$ 200,00 | AC003506 | negar |
| GBH437710 | reenviar_produto | 3 | R$ 389,70 | R$ 200,00 | AC004286 | escalar |
| GBH445947 | reenviar_produto | 2 | R$ 215,60 | R$ 200,00 | AC003938 | negar |
| GBH447425 | reenviar_produto | 3 | R$ 416,40 | R$ 200,00 | AC004634 | pedir_aprovacao |
| GBH448704 | reenviar_produto | 2 | R$ 233,82 | R$ 200,00 | AC004262 | escalar |
| GBH454448 | reenviar_produto | 2 | R$ 227,42 | R$ 200,00 | AC004058 | pedir_aprovacao |
| GBH457092 | reenviar_produto | 2 | R$ 245,60 | R$ 200,00 | AC004391 | pedir_aprovacao |
| GBH459387 | reenviar_produto | 2 | R$ 312,92 | R$ 200,00 | AC004522 | pedir_aprovacao |
| GBH459944 | reenviar_produto | 3 | R$ 437,10 | R$ 200,00 | AC004247 | pedir_aprovacao |
| GBH460900 | reenviar_produto | 2 | R$ 265,82 | R$ 200,00 | AC004403 | pedir_aprovacao |
| GBH463051 | reenviar_produto | 2 | R$ 391,20 | R$ 200,00 | AC004341 | pedir_aprovacao |
| GBH464541 | reenviar_produto | 2 | R$ 319,60 | R$ 200,00 | AC004684 | pedir_aprovacao |
| GBH465004 | reenviar_produto | 2 | R$ 319,20 | R$ 200,00 | AC004608 | pedir_aprovacao |
| GBH465801 | reenviar_produto | 2 | R$ 359,60 | R$ 200,00 | AC004733 | escalar |
| GBH468066 | reenviar_produto | 2 | R$ 279,60 | R$ 200,00 | AC004618 | pedir_aprovacao |
| GBH474725 | reenviar_produto | 2 | R$ 325,60 | R$ 200,00 | AC004840 | pedir_aprovacao |
| GCH523113 | reenviar_produto | 2 | R$ 398,62 | R$ 200,00 | AC000314 | pedir_aprovacao |
| GCH523956 | reenviar_produto | 3 | R$ 578,40 | R$ 200,00 | AC000326 | escalar |
| GCH525227 | reenviar_produto | 2 | R$ 377,60 | R$ 200,00 | AC000207 | escalar |
| GCH525282 | reenviar_produto | 2 | R$ 218,46 | R$ 200,00 | AC000106 | pedir_aprovacao |
| GCH525569 | reenviar_produto | 2 | R$ 387,60 | R$ 200,00 | AC000863 | pedir_aprovacao |
| GCH526097 | reenviar_produto | 3 | R$ 253,68 | R$ 200,00 | AC000865 | escalar |
| GCH526649 | reimprimir_personalizacao | 2 | R$ 360,82 | R$ 200,00 | AC000493 | escalar |
| GCH527016 | reenviar_produto | 2 | R$ 225,60 | R$ 200,00 | AC001299 | pedir_aprovacao |
| GCH527518 | reenviar_produto | 3 | R$ 308,40 | R$ 200,00 | AC001312 | pedir_aprovacao |
| GCH529021 | reenviar_produto | 2 | R$ 202,62 | R$ 200,00 | AC001011 | pedir_aprovacao |
| GCH529074 | reimprimir_personalizacao | 2 | R$ 314,62 | R$ 200,00 | AC001052 | escalar |
| GCH534776 | reenviar_produto | 2 | R$ 277,60 | R$ 200,00 | AC001912 | pedir_aprovacao |
| GCH536675 | reenviar_produto | 2 | R$ 245,60 | R$ 200,00 | AC002218 | pedir_aprovacao |
| GCH539889 | reenviar_produto | 2 | R$ 359,80 | R$ 200,00 | AC002871 | pedir_aprovacao |
| GCH541149 | reenviar_produto | 2 | R$ 329,80 | R$ 200,00 | AC002203 | pedir_aprovacao |
| GCH542937 | reenviar_produto | 2 | R$ 211,60 | R$ 200,00 | AC003649 | escalar |
| GCH544159 | reenviar_produto | 3 | R$ 269,73 | R$ 200,00 | AC003478 | escalar |
| GCH554557 | reenviar_produto | 2 | R$ 288,62 | R$ 200,00 | AC004605 | pedir_aprovacao |

## 2. Reclamações com anexo suspeito que receberam dinheiro

**280** conversas com anexo e pedido identificado. O verificador marca
**25** como suspeitas. Dessas, **23** receberam reenvio, reimpressão,
troca ou reembolso no histórico. Com o agente, iriam para o supervisor (`sinalizar_suspeita`)
antes de qualquer gasto.

**Custo evitado estimado: R$ 1.356,91** (soma de valor do pedido × 0,45
nas 23 conversas, `parametros.md`: custo de reenviar/reembolsar uma reclamação que
não procede). É um valor esperado: suspeita não é fraude confirmada, e o supervisor pode aprovar.

| ação recebida | conversas suspeitas |
|---|---|
| reenviar_produto | 23 |

| sinal | conversas suspeitas com o sinal |
|---|---|
| captura_antes_da_entrega | 11 |
| editor_de_imagem | 10 |
| hash_repetido | 9 |
| sem_exif | 7 |

| conversa | pedido | sinais | ações com dinheiro | valor do pedido | custo evitado |
|---|---|---|---|---|---|
| AT104936 | GCH525527 | captura_antes_da_entrega | reenviar_produto | R$ 92,80 | R$ 41,76 |
| AT106397 | GBH375448 | editor_de_imagem | reenviar_produto | R$ 162,80 | R$ 73,26 |
| AT106985 | GCH529021 | captura_antes_da_entrega | reenviar_produto | R$ 101,31 | R$ 45,59 |
| AT107296 | GCH532004 | captura_antes_da_entrega | reenviar_produto | R$ 186,91 | R$ 84,11 |
| AT107636 | GCH532504 | captura_antes_da_entrega | reenviar_produto | R$ 64,90 | R$ 29,21 |
| AT108179 | GCH533082 | hash_repetido, sem_exif | reenviar_produto | R$ 205,80 | R$ 92,61 |
| AT108528 | GCH535004 | captura_antes_da_entrega | reenviar_produto | R$ 87,80 | R$ 39,51 |
| AT109113 | GCH535078 | captura_antes_da_entrega | reenviar_produto | R$ 123,80 | R$ 55,71 |
| AT109619 | GCH539223 | editor_de_imagem | reenviar_produto | R$ 79,90 | R$ 35,96 |
| AT110620 | GCH541547 | captura_antes_da_entrega, hash_repetido, sem_exif | reenviar_produto | R$ 90,80 | R$ 40,86 |
| AT111493 | GCH542100 | hash_repetido, sem_exif | reenviar_produto | R$ 205,80 | R$ 92,61 |
| AT111900 | GCH545147 | captura_antes_da_entrega, hash_repetido | reenviar_produto | R$ 84,81 | R$ 38,16 |
| AT112299 | GCH544744 | captura_antes_da_entrega, hash_repetido | reenviar_produto | R$ 132,80 | R$ 59,76 |
| AT113281 | GCH547544 | hash_repetido, sem_exif | reenviar_produto | R$ 133,56 | R$ 60,10 |
| AT114498 | GCH551285 | captura_antes_da_entrega, hash_repetido, sem_exif | reenviar_produto | R$ 97,80 | R$ 44,01 |
| AT114539 | GBH454818 | editor_de_imagem | reenviar_produto | R$ 109,80 | R$ 49,41 |
| AT114633 | GBH454299 | editor_de_imagem | reenviar_produto | R$ 161,82 | R$ 72,82 |
| AT114996 | GCH552901 | captura_antes_da_entrega, hash_repetido | reenviar_produto | R$ 98,91 | R$ 44,51 |
| AT115189 | GBH459078 | editor_de_imagem | reenviar_produto | R$ 159,80 | R$ 71,91 |
| AT115570 | GBH459183 | editor_de_imagem, sem_exif | reenviar_produto | R$ 148,23 | R$ 66,70 |
| AT115610 | GCH555045 | hash_repetido, sem_exif | reenviar_produto | R$ 182,80 | R$ 82,26 |
| AT115694 | GBH464417 | editor_de_imagem | reenviar_produto | R$ 139,80 | R$ 62,91 |
| AT115768 | GBH461466 | editor_de_imagem | reenviar_produto | R$ 162,60 | R$ 73,17 |

## 3. Categoria: o leitor do agente contra a tag humana

O leitor (`atendimento.agente.leitor.ler`) leu as mensagens do cliente de
**2984** conversas. **330** não têm mensagem do cliente (só o bot falou) e ficam
fora da conta. Nas **2654** restantes, a categoria do leitor bate com a
`tag_agente` em **1595** (60,1%).

| tag humana | conversas | acertos | acerto | o leitor disse (erros mais comuns) |
|---|---|---|---|---|
| Rastreio | 616 | 430 | 69,8% | Atraso (148), Outros (15) |
| Atraso | 466 | 343 | 73,6% | Rastreio (83), Outros (27) |
| Avaria | 213 | 165 | 77,5% | Produto faltando (23), Outros (12) |
| Dúvida | 187 | 36 | 19,3% | Outros (82), Rastreio (33) |
| Produto faltando | 178 | 155 | 87,1% | Avaria (12), Outros (10) |
| Outros | 178 | 24 | 13,5% | Rastreio (52), Atraso (27) |
| Troca | 158 | 85 | 53,8% | Avaria (21), Cancelamento (15) |
| Cancelamento | 156 | 94 | 60,3% | Atraso (33), Financeiro (20) |
| Financeiro | 138 | 43 | 31,2% | Outros (58), Atraso (18) |
| Endereço | 118 | 75 | 63,6% | Rastreio (34), Atraso (5) |
| Promoção | 105 | 96 | 91,4% | Outros (7), Dúvida (2) |
| Reclamação produto | 104 | 21 | 20,2% | Avaria (38), Produto faltando (18) |
| Elogio | 37 | 28 | 75,7% | Outros (6), Promoção (2) |

As três tags com menor acerto são Outros (13,5% de 178); Dúvida (19,3% de 187); Reclamação produto (20,2% de 104). É por elas que o classificador
melhora primeiro.

### Escalações corretas (casos sensíveis)

Critério: o leitor marca a conversa como sensível quando a categoria é `reacao_adversa`
(o agente escala para a supervisão, HG-06). No histórico, conta como **escalação humana** a
conversa com `registrar_cosmetovigilancia` (só supervisor) ou com alguma ação com
`aprovado_por` em `acoes_executadas_sistemas.csv`; o histórico não registra `acionar_pessoa`.

| medida | conversas |
|---|---|
| sensíveis pelo leitor (reação adversa) | 27 |
| dessas, com escalação humana no histórico | 27 (100,0%) |
| conversas com cosmetovigilância registrada pelo time | 27 |
| dessas, marcadas como sensíveis pelo leitor | 27 (100,0%) |

## Consultas de origem

Tudo sai de `python -m atendimento.avaliacao` (lê `docs/` com o módulo `csv`, UTF-8,
separador `,`, somente leitura). Código: `src/atendimento/avaliacao/`.

| número | consulta |
|---|---|
| ações com dinheiro | `acoes_executadas_sistemas.csv`: linhas com `acao` em reembolsar, reenviar_produto, reimprimir_personalizacao, trocar_produto e `valor_rs` preenchido, em ordem de `data_hora`, `acao_id` |
| decisão do agente | `atendimento.politicas.decidir` para cada linha, com "agora" = `data_hora` da ação; `acoes_anteriores` = linhas anteriores do mesmo `order_id`; `aprovado_por` do histórico vira aprovação; papel por `equipe_atendimento.cargo` de `executado_por`; categoria por `historico_conversas.tag_agente` → `politicas.csv` `categorias.*.tag_equivalente`; pedido de `pedidos.csv` (`data_separacao`, `data_entrega`) |
| divergência | decisão do agente ≠ `executar` (o time executou todas as ações); motivo pela `regra` da decisão |
| limites | `politicas.csv`: `limites_por_papel.atendente.reembolso_max_rs`, `reenvio_ou_reimpressao_max_rs`, `troca_max_rs` |
| M11 | `acoes_executadas_sistemas.csv` agrupado por (`order_id`, `acao`): 2+ `conversation_id` distintos, `aprovado_por` vazio em todas, cada `valor_rs` ≤ limite, soma > limite (mesma regra de `ingestao/baseline_metricas.md`, M11) |
| conversas com anexo | `anexos_conversas.csv` agrupado por `conversation_id`; pedido por `historico_conversas.order_id` (ou `anexos_conversas.order_id`) em `pedidos.csv` + `itens_pedido.csv` |
| suspeita | `atendimento.verificacao.verificar`, com anexos do mesmo `hash_perceptual` enviados antes (`enviado_em`) e reenvios do cliente em `trocas_reenvios.csv` (`tipo` = reenvio, EC-19) com `data_solicitacao` < `historico_conversas.data_abertura` |
| receberam dinheiro | conversa suspeita com ao menos uma ação com dinheiro em `acoes_executadas_sistemas.csv` (mesmo `conversation_id`) |
| acerto de categoria | `historico_mensagens.csv` com `autor` = cliente, por `conversation_id` em ordem de `timestamp`; `atendimento.agente.leitor.ler` no texto; categoria → `politicas.csv` `categorias.*.tag_equivalente` (rastreio → onde_esta_pedido, atraso → atraso_entrega, arrependimento → arrependimento_cancelamento; sem tag_equivalente → "Reclamação produto"; outros → "Outros"); comparação com `historico_conversas.tag_agente` |
| custo evitado | soma de `VeredictoEvidencia.custo_aceitar_falso_rs` = `pedidos.valor` × 0,45 (`parametros.md`) nessas conversas |

## Premissas e limites

- O histórico é reexecutado como aconteceu: a soma por pedido usa as ações que o time de fato
  executou antes, mesmo as que o agente teria segurado.
- A categoria vem da `tag_agente` humana. "Reclamação produto" e "Outros" não têm categoria em
  `politicas.csv`; nelas o motor aplica só a alçada (sem prazo, sem caso sensível).
- Ações aprovadas no histórico contam como aprovação válida (o aprovador é supervisor), mas
  entram na soma da alçada do pedido (Q10): uma aprovação cobre só a ação aprovada.
- "Financeiro" junta cobrança duplicada e pagamento pendente; o leitor só tem a primeira.
- Escalações corretas medem só casos sensíveis (reação adversa); escalações por alçada estão
  na seção 1.
