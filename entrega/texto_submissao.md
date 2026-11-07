# FIO, o colega de atendimento (Gocase / GoBeauté)

Texto de submissão do desafio Atendimento ao Cliente, GoHacks Talent 2026.

## Problema

O atendimento da Gocase e da GoBeauté recebe cerca de 4.000 conversas por mês, por WhatsApp, e-mail e Reclame Aqui (`docs/parametros.md`). Uma conversa costuma exigir trabalho em vários sistemas: na média, uma pessoa gasta 12,2 minutos e passa por 1,83 sistemas, de 11 que aparecem no log de ações (M3). O Reclame Aqui tem 11,6% das conversas e 50,4% do custo, a R$ 42 cada (M1, M12). Do histórico, 32,9% são conversas repetidas sobre o mesmo pedido (M4). E parte das fotos enviadas como prova levanta dúvida: 17 reaparecem em pedidos diferentes, 11 foram tiradas antes da entrega e 10 passaram por editor de imagem (M6).

## Solução

O FIO é um agente que trabalha como um colega do time. O nome vem do que ele faz: segue o fio de cada pedido pelos sistemas e acha a causa comum dos contatos repetidos. Às 8h ele pega a fila, lê cada conversa, consulta pedido, rastreio, pagamento e anexos pelos IDs e age nos sistemas: abre chamado na transportadora, informa status, reenvia, troca ou reembolsa, sempre dentro da alçada de atendente. Quando passa disso, ele pede aprovação ao supervisor no canal do time, com a evidência na própria mensagem. Esse canal está na interface e também no Slack. Quando a foto não bate com o pedido, ele segura o dinheiro e sinaliza a suspeita. Reação adversa a produto vai direto para o supervisor. Ao ver um padrão, chama um segundo agente, o analista, que abre o incidente.

## O que provamos

A PoC prova duas frentes, a verificação da reclamação e a autonomia com escalação, e executa a ação no fim. Na demo, o FIO trabalha a fila real das 8h (65 conversas):

- Às 8h20, sem ninguém perguntar, posta no canal do time 19 avisos de SLA: um e-mail já vencido e as conversas de WhatsApp perto do prazo.
- Ao processar a fila, termina com 34 conversas resolvidas sozinho, 2 aguardando aprovação, 18 aguardando o cliente, 0 suspeitas e 11 escaladas, e o placar mostra R$ 636,00 de custo evitado. As 18 são pedidos de foto, e o FIO não as conta como resolvidas.
- Escala a reação adversa (`AT116568`) com a orientação de suspender o uso.
- Pede aprovação para um reembolso acima de R$ 100, que outro supervisor aprova pelo canal. A autoaprovação é recusada com HTTP 403.
- No Slack, o FIO posta só o que pede ação de uma pessoa, com botões, e um resumo de cada rodada. O supervisor aprova com um clique no `#atendimento-ops` e a ação sai no log dos sistemas com quem aprovou. Só aprova pelo Slack quem está mapeado como supervisor, e a regra é a mesma da interface. Quem é do time pode perguntar ao `@FIO` o status de um pedido. Se o colaborador pedir dinheiro, o pedido passa pela mesma política e, acima da alçada, vira pedido de aprovação. Se o Slack cair, o agente continua, e o canal do time da interface faz o mesmo papel.
- O agente analista trata o padrão de cobrança em dobro: 12 pedidos com duas cobranças e nenhum estorno (M7). Ele abre um incidente e avisa só os clientes que aceitam contato: na jornada gravada foram 11 avisos, e 1 cliente ficou de fora por falta de consentimento.

Um modo replay reexecuta reclamações antigas: o FIO sinaliza a suspeita com as evidências, o cliente recebe uma resposta neutra, e um supervisor decide na tela se a reclamação procede. Quem sinalizou não pode decidir. A jornada completa no navegador passou nas 20 verificações automáticas às 10:59, antes de a decisão da suspeita entrar na tela (`.scratch/e2e/relatorio.json`), e o vídeo está em `apresentacao/midia/demo.mp4`. As outras três frentes (triagem, resolução multissistema e prevenção) estão num protótipo navegável.

## Números medidos

Reexecutamos o motor de políticas, o verificador e o leitor de mensagens sobre o histórico (`ingestao/avaliacao_offline.md`, gerado por `uv run python -m atendimento.avaliacao`):

- 64 de 64 casos em que cada ação cabia na alçada, mas a soma no mesmo pedido passou do limite sem aprovação, foram barrados antes de o dinheiro sair.
- 23 reenvios foram feitos em conversas com foto suspeita. Com o FIO, iriam ao supervisor antes de qualquer gasto, com custo evitado estimado de R$ 1.356,91 (45% do valor de cada pedido, `docs/parametros.md`). É um valor esperado: suspeita não é fraude confirmada, e o supervisor pode aprovar.
- O leitor por regras do FIO classifica a conversa igual à tag do time em 60,1% dos casos: 1.595 de 2.654 conversas com mensagem do cliente (seção 3 da mesma avaliação). Os acertos mais baixos estão em Outros (14,0%), Reclamação produto (19,2%) e Dúvida (19,3%).
- O leitor também pode ser o Claude (`ATENDIMENTO_LLM=1`). Numa amostra de 300 conversas estratificada pela tag, o acerto subiu de 53,7% (regras) para 62,0% (Claude), e Dúvida foi de 17,4% para 39,1% (`ingestao/avaliacao_leitor_claude.md`). As 27 conversas de cosmetovigilância e as 3 com instrução embutida continuaram detectadas. O Claude só lê o texto já mascarado e só classifica: quem decide é o motor de políticas, e qualquer falha da API volta para as regras. Uma rodada da fila de 65 conversas custa cerca de US$ 0,50, e as respostas ficam em cache, então repetir a mesma fila não custa nada.

A linha de base do problema está em `ingestao/baseline_metricas.md` (códigos M1 a M12). O histórico é uma amostra de 1 em cada 4 clientes; a fila está em volume cheio.

## Salvaguardas

- A alçada é somada por pedido: até R$ 200 para reenvio, reimpressão ou troca e R$ 100 para reembolso (`docs/politicas.csv`). Acima disso, o supervisor aprova, e ninguém aprova a própria ação.
- Suspeita não vira acusação: um supervisor que não a sinalizou decide, com as evidências e uma justificativa por escrito. O cliente só fica sabendo que o pedido está em análise. Foto sem metadados, sozinha, não é suspeita.
- Em reação adversa, o FIO orienta a suspensão do uso na hora, e a cosmetovigilância fica com o supervisor.
- CPF, cartão e telefone saem mascarados em resposta, log e tela. Aviso proativo só vai para quem aceitou contato pelo canal.
- A mensagem do cliente é tratada como dado: uma instrução escrita pelo cliente não muda o que o FIO faz.
- Cada papel só usa as ferramentas a que tem permissão. Uma ação com dinheiro repetida não paga duas vezes.

## Próximos passos

1. Triagem: o vigia já avisa o time do SLA; falta ordenar a fila pelo prazo e pelo custo do canal. Às 8h, 18 conversas de WhatsApp sem resposta humana vencem o SLA às 8h30 (M5).
2. Prevenção: transformar padrões de atraso por transportadora e região em incidente e aviso proativo, respeitando o consentimento e o limite de 300 avisos por dia.
3. Canal do time: renovar sozinho o token do Slack, que hoje vence em cerca de 12 h e precisa ser conferido antes de cada uso.
4. Leitor e avaliação: medir o leitor com Claude no histórico inteiro, atacar as categorias em que nenhum dos dois acerta bem (Outros e Troca) e medir também as escalações corretas.
