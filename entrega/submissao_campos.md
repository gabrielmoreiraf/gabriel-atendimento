# Campos da submissão (formulário GoHacks, até 16:30)

Cada texto respeita o limite do campo. Copie e cole como está.

## Nome do projeto (80/80)

FIO: o colega de atendimento que confere a reclamação antes de mexer no dinheiro

## Qual problema você resolveu? (537/600)

Uma loja como a Gocase recebe cerca de 4.000 contatos por mês por WhatsApp, e-mail e Reclame Aqui. Cada um custa 12,2 minutos de uma pessoa que passa por até 4 dos 11 sistemas da empresa: pedido, portal da transportadora, gateway, trocas. O Reclame Aqui tem 11,6% das conversas e 50,4% do custo, e 32,9% dos contatos são o mesmo cliente voltando pelo mesmo pedido. Nem toda avaria é real: na base, há fotos repetidas em pedidos diferentes, tiradas antes da entrega ou editadas. Hoje a atendente decide isso no olho, com dinheiro em jogo.

## Qual é a sua solução? (722/800)

O FIO pega a fila das 8h e trata cada conversa como uma atendente faria. Lê a mensagem, consulta pedido, rastreio, pagamento e anexos, confere se a foto é deste pedido e se foi tirada depois da entrega, e passa tudo por um motor de políticas. Dentro da alçada ele age: reenvia, estorna ou abre chamado, com referência no log. Acima do limite, em caso sensível ou com foto suspeita, chama a pessoa certa no Slack do time. O supervisor aprova com um botão e quem pediu não aprova a própria ação. Reação adversa a cosmético é escalada com orientação de suspender o uso. Um agente analista detecta padrões, como cobrança em dobro, e abre um incidente único. A tela mostra a fila, o caso, o console das ações e o canal do time.

## Como você usou a IA? (761/800)

Usei o Claude Code como orquestrador de seis agentes em paralelo no Orca, cada um com uma parte do código e regras fixas no AGENTS.md: requisitos em BDD, TDD com o ID do cenário em cada teste e um agente revisor separado, que é o único que aprova uma funcionalidade. Ele reprovou várias entregas e achou erros reais: um pedido pelo Slack que pulava a política de reembolso, uma alçada que dava para fatiar e 4 relatos de reação adversa que o leitor deixava passar. No produto, o Claude só lê a mensagem do cliente, com CPF, telefone e nome mascarados antes da API; quem decide é o motor de políticas. Na mesma amostra de 300 conversas, o acerto de categoria foi de 53,7% (regras) para 62,0% (Claude). Toda métrica vem de uma consulta reproduzível sobre os CSVs.

## Qual o resultado ou impacto esperado? (459/500)

Na fila real das 8h (65 conversas), o FIO resolveu 34 sozinho, pediu foto em 18, levou 2 para aprovação e escalou 11. Reexecutado sobre o histórico, o motor barrou 64 de 64 casos em que o time passou da alçada somando ações no mesmo pedido, e segurou 23 reenvios com foto suspeita, com custo evitado estimado de R$ 1.356,91. Reconheceu 27 de 27 relatos de reação adversa. O ganho é tempo de atendente nos casos simples e dinheiro protegido nos casos de risco.

## Slides (PDF)

`apresentacao/FIO_pitch.pdf` (10 páginas).

## Link do GitHub

https://github.com/gabrielmoreiraf/fio-atendimento
