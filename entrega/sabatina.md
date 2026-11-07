# Sabatina (5 min): respostas curtas

Duas frases e, quando der, algo para mostrar na tela. Se não souber: "Não cheguei lá ainda, mas o próximo passo seria…".

## As quatro perguntas da tabela do evento

**Como isso funciona tecnicamente?**
O Claude lê a mensagem e um motor de políticas em Python decide, lendo pedido, pagamento e anexos por ID, com as regras e os limites de `politicas.csv`. Mostre o console: cada ação tem sistema, valor, quem executou, quem aprovou e a referência.

**Quem usaria isso na prática?**
A atendente, que deixa de passar por quatro sistemas nos casos simples, e o supervisor, que aprova pelo Slack o que passa da alçada. Mostre o pedido de aprovação no `#atendimento-ops`.

**O que falta para funcionar?**
Ligar as ferramentas às APIs reais (ERP, gateway, portais das transportadoras), que hoje são simuladas sobre a base do desafio. Faltam também padrões por transportadora e região no agente analista e a persistência do estado num banco.

**Como medir o sucesso?**
Métrica de processo: a parte da fila resolvida sem pessoa, hoje 34 de 65 na fila das 8h. Impacto no negócio: dinheiro segurado em reclamação suspeita e zero ação acima da alçada sem aprovação, medidos contra o histórico (64 de 64 barrados).

## Outras prováveis

**Quanto custa o Claude?**
Uma rodada da fila completa custa cerca de US$ 0,50, com cache para não pagar duas vezes pelo mesmo texto. Sem chave, o FIO funciona com o leitor por regras.

**E se o modelo errar?**
O modelo só classifica; o dinheiro passa pela política e pela alçada. Reação adversa e instrução embutida são detectadas também pelas regras, e se a API falhar ele volta para as regras.

**E os dados pessoais (LGPD)?**
CPF, cartão, telefone, e-mail e nome completo são mascarados antes de qualquer saída: API do Claude, Slack, tela e log. A base não vai para o GitHub.

**Por que não é um chatbot?**
Todo caso termina com uma ação registrada num sistema ou com uma escalação para uma pessoa. Mostre o console e o canal do time.

**Escala?**
A leitura das mensagens roda em paralelo, e a decisão é por regras, então o custo cresce com o volume de leitura, não com regras novas.

**Como você conferiu o que a IA fez?**
Um agente revisor separado aprovava cada funcionalidade só com teste e evidência, e reprovou várias entregas. Ele achou uma brecha em que um pedido pelo Slack pulava a política de reembolso, e eu corrigi antes de aprovar.
