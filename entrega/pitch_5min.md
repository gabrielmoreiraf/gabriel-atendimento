# Pitch do FIO em 5 minutos

Segue a linha do tempo do Toolkit do evento. Se faltar tempo, corte fala, nunca a demo. Deck: `apresentacao/FIO_pitch.pdf` (tecla N mostra as notas com as fontes). App: `URL_DO_APP` (ou `http://localhost:5173`). Plano B: `apresentacao/midia/demo.mp4`.

## 0:00 a 0:15 · Abertura (slide 1)

"Sou o Gabriel, fiz o desafio de Atendimento ao Cliente. Construí o FIO, um colega de atendimento que confere a reclamação antes de mexer no dinheiro."

## 0:15 a 0:50 · Dor e usuária-chave (slide 2)

"A Ana é atendente da Gocase. Toda manhã ela abre a fila e, em cada conversa, passa por até quatro sistemas: o pedido no ERP, o portal da transportadora, o gateway e as trocas. São 12,2 minutos por contato, cerca de 4.000 contatos por mês. O Reclame Aqui tem 11,6% das conversas e metade do custo, e um terço dos contatos é o mesmo cliente voltando pelo mesmo pedido."

## 0:50 a 1:20 · Fluxo atual (slide 2, mesma tela)

"Quando chega uma avaria, a Ana olha a foto e decide no olho. Na base há fotos repetidas em pedidos diferentes, tiradas antes da entrega ou editadas. Se ela reenvia sem conferir, a empresa perde 45% do pedido. Se nega uma reclamação verdadeira, perde o cliente."

## 1:20 a 2:10 · Solução com IA (slide 3)

"Minha solução é o FIO: um agente de IA que confere a reclamação, age nos sistemas dentro da alçada e chama a pessoa certa quando não pode decidir, para que a Ana só cuide do que precisa dela. Ele lê, consulta, confere, decide pela política e age, com registro de cada ação. O Claude só lê a mensagem; quem decide é o motor de políticas. Deixa eu mostrar como isso funciona na prática."

## 2:10 a 3:30 · Demo (app)

1. Clique em "Avançar o relógio para 08:20": os alertas de SLA chegam no canal do time.
2. "Processar fila": as 65 conversas são tratadas. Mostre o placar (34 resolvidas sozinho, 18 aguardando foto, 2 em aprovação, 11 escaladas) e o console com as ações e as referências.
3. Abra a AT116568: reação adversa escalada, com orientação de suspender o uso.
4. Verificação de evidência: processe a AT104936. Foto tirada antes da entrega e hash repetido: vira suspeita, e o cliente recebe só "está em análise".
5. Slack `#atendimento-ops`: aprovação do reembolso acima de R$ 100. Clique em Aprovar como supervisor e mostre a ação aparecendo no console.

Se algo falhar, abra o vídeo `apresentacao/midia/demo.mp4` e siga narrando.

## 3:30 a 4:00 · Métricas (slide 9)

"Reexecutei o motor sobre o histórico: ele barrou 64 de 64 casos em que o time passou da alçada somando ações no mesmo pedido, e segurou 23 reenvios com foto suspeita, um custo evitado estimado de R$ 1.356,91. Reconheceu 27 de 27 relatos de reação adversa."

## 4:00 a 5:00 · Impacto e implantação (slide 10)

"No dia a dia, a Ana para de copiar dados entre quatro sistemas nos casos simples e só entra quando o FIO pede, no Slack. A primeira dependência é ter acesso de leitura e escrita às APIs do ERP, do gateway e das transportadoras. Na segunda-feira eu ligaria o FIO em modo sombra numa fila real: ele decide, uma pessoa confere, e medimos o acerto antes de dar autonomia."
