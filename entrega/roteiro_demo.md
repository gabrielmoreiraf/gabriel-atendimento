# Roteiro da demo ao vivo do Gabriel (3 a 4 minutos)

O Gabriel é o colega de atendimento da Gocase e da GoBeauté. Ele segue o fio de cada pedido pelos sistemas e acha a causa comum dos contatos repetidos.

Quatro janelas:

1. **Deck:** `apresentacao/index.html` (setas para navegar; `#9` na URL abre o slide 9; tecla `N` mostra as notas com as fontes).
2. **Protótipo 360°:** `prototipo/index.html` (estático, abre sem servidor).
3. **App da PoC:** `http://localhost:5173` (interface React do W5), falando com a API do W4 em `http://localhost:8000`.
4. **Slack, canal `#atendimento-ops`:** lado a lado com o app, metade da tela para cada um. O Gabriel posta ali só o que pede ação de uma pessoa, com botões, e um resumo de cada rodada. O resto continua no **Canal do time** do app.

Deixe também um terminal pronto para os passos 7 e 9 e o vídeo `apresentacao/midia/demo.mp4` aberto e pausado no player, para o plano B. O vídeo é a jornada E2E das 10:59, com 20 de 20 verificações aprovadas, e não tem o Slack. O placar dele é de antes do último ajuste do leitor (29 resolvidas e 16 escaladas): não leia esses números em voz alta.

## Antes de subir no palco (5 min antes)

- [ ] **Token do Slack válido.** O token do bot tem rotação e vence em cerca de 12 h. Confira antes de reiniciar:
  ```bash
  uv run python -c "import os, dotenv; dotenv.load_dotenv(); from slack_sdk import WebClient; r = WebClient(os.environ['SLACK_BOT_TOKEN']).auth_test(); print(r['ok'], r['team'], r['user'])"
  ```
  Deve imprimir `True` com o nome do workspace e do bot. Se der `token_expired` ou `invalid_auth`, gere um token novo na configuração do app no Slack, troque `SLACK_BOT_TOKEN` no `.env` e só então reinicie.
- [ ] **Reiniciar o backend.** O estado do Gabriel vive em memória, os avisos do vigia só saem uma vez por execução da API e a conexão com o Slack abre na subida. Reinicie sempre, **sem `--reload`**, para que uma edição em `src/` não reinicie a API no meio da demo:
  ```bash
  uv run uvicorn atendimento.api.app:app --port 8000
  ```
  O `.env` precisa ter `ATENDIMENTO_SLACK=1`, os três tokens do Slack e o seu usuário do Slack mapeado para `supervisor_02` em `SLACK_SUPERVISORES`. Na saída do uvicorn deve aparecer `Canal do time espelhado no Slack`. Se aparecer `Slack não ligou`, a demo segue pelo plano B do passo 8.
- [ ] **Leitor: regras ou Claude.** O padrão é o leitor por regras (`ATENDIMENTO_LLM=0`), determinístico, e o placar do passo 4 vale para ele. Com `ATENDIMENTO_LLM=1` e `ANTHROPIC_API_KEY` no `.env`, quem lê as mensagens é o Claude:
  - numa amostra de 300 conversas, ele acertou a categoria em 62,0% contra 53,7% das regras (`ingestao/avaliacao_leitor_claude.md`);
  - uma rodada da fila custa cerca de US$ 0,50 (65 conversas; a medição de 300 custou US$ 2,37);
  - as respostas ficam em cache em `var/cache_leitor_claude`, por hash do texto mascarado. Rode a fila uma vez no ensaio e reinicie: na demo, a mesma fila sai do cache, sem custo e sem depender da rede;
  - se a API do Claude falhar, o Gabriel volta sozinho para as regras;
  - o placar pode sair diferente de 34 / 2 / 18 / 0 / 11. Anote no ensaio os números que aparecerem e fale esses.
- [ ] **A API responde?** `curl -s -m 5 localhost:8000/api/placar` deve trazer tudo zerado. Entre 10:49 e 10:53 ela travou e não respondia a GET.
- [ ] **Bot no canal.** O Gabriel precisa ser membro do `#atendimento-ops` para receber o `@Gabriel`.
- [ ] **Botões da suspeita na tela.** A decisão da suspeita (passo 7) chegou ao app às 11:18 e não estava no vídeo nem no E2E das 10:59. No ensaio, confira se, depois de **Verificar** o `AT104936`, aparecem **Procedente** e **Improcedente**. Se não aparecerem, use o plano B do passo 7.
- [ ] **Deck no slide 1**, protótipo no mapa, app recarregado com a fila visível e o relógio em 08:00, e o `#atendimento-ops` aberto ao lado, rolado até o fim.
- [ ] **Zoom do navegador em 125%** no app, para a banca ler de longe.
- [ ] **Terminal com os comandos dos passos 7 e 9 colados**, ainda não executados.

## Passo a passo

Os tempos são acumulados. O que está entre aspas é a frase para dizer.

### 1. A dor (0:00 a 0:15) · Deck, slides 1 e 2

- **Dizer:** "O Reclame Aqui tem 11,6% das conversas e metade do custo, e cada conversa toma 12 minutos de uma pessoa abrindo sistema por sistema."
- **Mostrar:** slide 1 (capa) → seta → slide 2 (custo por canal).
- **Plano B:** se o deck não abrir, fale a frase em cima do mapa do passo 2.

### 2. A visão 360° (0:15 a 0:30) · Protótipo, `index.html`

- **Dizer:** "O Gabriel cobre as cinco frentes do atendimento. Em amarelo está onde uma pessoa decide, e hoje vamos provar ao vivo a verificação da reclamação e a escalação."
- **Mostrar:** o mapa. Passe o cursor pela linha amarela "Pessoa decide" e pare nas colunas F3 e F4, com o selo "Provado na PoC".
- **Plano B:** slide 4 do deck ("Cinco frentes…").

### 3. A fila das 08h e o vigia das 08:20 (0:30 a 0:50) · App, fila e "Canal do time"

- **Dizer:** "São 8h de 02/11, com 65 conversas abertas. Sem ninguém perguntar, o Gabriel olha o relógio e avisa o time do que vai estourar o prazo."
- **Mostrar:** a fila à esquerda (65 itens) e o placar zerado. No **Canal do time**, clique em **Avançar o relógio para 08:20**. Chegam **19 avisos de SLA**: o e-mail `AT116480`, que já passou do prazo, e as conversas de WhatsApp perto de vencer. Cada aviso diz o impacto e de quem o Gabriel espera ação.
- **Plano B:** prints `.scratch/e2e/01-inicio.png` e `02-vigia-canal.png`.

### 4. Processar fila (0:50 a 1:15) · App

- **Dizer:** "Um clique, e ele trata cada conversa: consulta o pedido, abre chamado na transportadora, responde o cliente e registra tudo no log. Quando falta foto, ele pede e espera, sem contar como resolvido."
- **Mostrar:**
  - botão **Processar fila** no placar;
  - o **Console dos sistemas** enchendo de ações;
  - o placar, que deve chegar a **34 resolvidas sozinho, 2 aguardando aprovação, 18 aguardando cliente, 0 suspeitas e 11 escaladas**, com **R$ 636,00** de custo evitado;
  - se der tempo, `AT116666`, em que ele pediu foto do produto e da embalagem;
  - no Slack, ao lado, chegam o resumo da rodada e os 2 pedidos de aprovação, já com os botões **Aprovar** e **Rejeitar**. Não clique ainda: fica para o passo 8.
- **Plano B:** print `.scratch/e2e/03-fila-processada.png` (e `08-aguardando-cliente.png` para os pedidos de foto), ou `demo.mp4` a partir do início. O placar dos prints e do vídeo é o antigo. Se o Slack não mostrar nada, siga só com o app.

### 5. Reação adversa escalada (1:15 a 1:35) · App, conversa `AT116568`

- **Dizer:** "Aqui ele não resolve sozinho: a cliente teve reação ao produto. Ele orienta a suspender o uso e passa o caso ao supervisor, que registra a cosmetovigilância."
- **Mostrar:** clique em `AT116568` na fila. No painel do caso:
  - estado **escalada**;
  - **Decisão da política** = Escalar, pela regra `categorias.reacao_adversa.acoes_obrigatorias`;
  - **Resposta enviada ao cliente:** manda suspender o uso e diz que uma pessoa fala com ela em até 24 h.
- **Plano B:** print `.scratch/e2e/04-caso-reacao-adversa.png`.

### 6. Verificação de evidência no histórico (1:35 a 2:00) · App, seção "Verificação de evidência"

- **Dizer:** "Agora a frente de fraude, rodando sobre uma reclamação antiga, no dia em que ela chegou. A foto foi tirada antes de o pedido ser entregue e já tinha aparecido em outro pedido. O Gabriel segura o reenvio, manda para o supervisor, e o cliente recebe só uma resposta neutra."
- **Mostrar:** link **Verificação de evidência** no topo. Use `Cmd+F` e procure `AT104936` (a lista tem 280 conversas com foto). Clique em **Verificar** e aponte:
  - **Sinais do verificador:** captura anterior à entrega, hash repetido e reenvios anteriores do cliente;
  - **Decisão da política:** sinalizar suspeita, para o supervisor decidir;
  - **Resposta ao cliente:** "Recebemos sua solicitação e ela está em análise pela nossa equipe. Retornamos em até 24 horas." Sem acusação.
- **Plano B:** print `.scratch/e2e/09-replay-evidencia.png`, ou o slide 5 do deck ("Antes de reenviar, ele confere se a foto é deste pedido").

### 7. O supervisor decide a suspeita (2:00 a 2:20) · App, mesmo caso

- **Dizer:** "Quem decide a suspeita é o supervisor, e quem sinalizou não decide. Ele lê as evidências, escreve o motivo e escolhe procedente ou improcedente."
- **Mostrar:**
  - no bloco da suspeita do `AT104936` (aparece também no **Canal do time**), o prazo para decidir, 24 h depois da sinalização;
  - o campo **Supervisor que decide**, que não oferece quem sinalizou;
  - em **Justificativa da decisão**, um texto curto, por exemplo "Foto repetida em outro pedido e tirada antes da entrega";
  - o clique em **Improcedente**. A resposta ao cliente muda para a negativa educada, que convida a mandar novas fotos e não acusa ninguém.
  - Se escolher **Procedente**, o Gabriel segue a política do caso: executa o reenvio ou pede aprovação, somando o que o pedido já recebeu.
  - Os botões só liberam depois de escrita a justificativa.
  - A mesma suspeita chega ao Slack com **Procedente** e **Improcedente**. Decida no app, para a banca ver a justificativa sendo escrita.
- **Plano B:** sem os botões na tela, mostre a regra pela API. Este comando pega a suspeita pendente e tenta decidi-la como `agente`, quem a sinalizou:
  ```bash
  SUS=$(curl -s localhost:8000/api/suspeitas | jq -r '.[0].suspeita_id')
  curl -s -w '\nHTTP %{http_code}\n' -X POST localhost:8000/api/suspeitas/$SUS/decidir \
    -H 'content-type: application/json' \
    -d '{"supervisor_id":"agente","decisao":"improcedente","justificativa":"teste"}'
  ```
  Saída esperada: HTTP 403, porque só o supervisor decide (`reclamacao_suspeita.quem_decide`). Sem terminal, cite o slide 5 e siga.

### 8. Aprovação no Slack (2:20 a 2:45) · Slack `#atendimento-ops` ao lado do app

- **Dizer:** "Cobrança em dobro de R$ 118,80. O limite dele para reembolso é R$ 100, então ele pede aprovação no Slack, onde o time já está. Quem aprova é um supervisor, não ele."
- **Mostrar:**
  - no Slack, a mensagem "Gabriel pediu aprovação" de `AT116677` (reembolsar R$ 118,80, pedido `GBH491723`, endereçada à supervisora do turno);
  - clique em **Aprovar**. Você aprova como `supervisor_02`, um supervisor diferente de quem pediu. A mensagem perde os botões e passa a dizer "Aprovado por supervisor_02 pelo Slack.";
  - no app, ao lado, o **Console dos sistemas** mostra o `reembolsar` executado, com o aprovador;
  - ainda no canal, escreva `@Gabriel status do GCH553818`. Ele responde na conversa com o status do pedido (em trânsito, sem entrega registrada) e registra a resposta no log de ações.
- **Plano B, se o Slack cair:** a tela **Canal do time** do app faz o mesmo. No pedido de aprovação de `AT116677`, escolha **Roberto Mendes** (o `supervisor_02`) no campo **Supervisor**, escreva um comentário curto e clique em **Aprovar**; o **Console dos sistemas** mostra o `reembolsar` do mesmo jeito. Pule o `@Gabriel`. Sem app também, use os prints `.scratch/e2e/05-canal-pedido-aprovacao.png`, `06-aprovando.png` e `07-acao-aprovada-console.png`. Nos prints, o pedido aprovado é o outro pendente, `AT116520` (reembolso de R$ 155,81, por arrependimento).

### 9. Autoaprovação recusada (2:45 a 2:55) · Terminal

- **Dizer:** "A tela nem oferece quem pediu como aprovador. E se alguém tentar direto na API, o Gabriel não consegue aprovar o próprio pedido."
- **Mostrar:** rode o comando já colado. Ele pega o pedido de aprovação ainda pendente (o reembolso de `AT116520`) e tenta aprovar como `agente`:
  ```bash
  APR=$(curl -s localhost:8000/api/canal | jq -r '[.[] | select(.tipo=="aprovacao" and .estado=="pendente")][0].aprovacao_id')
  curl -s -w '\nHTTP %{http_code}\n' -X POST localhost:8000/api/aprovacoes/$APR/aprovar \
    -H 'content-type: application/json' -d '{"supervisor_id":"agente"}'
  ```
  Saída esperada: `{"detail":"agente não é supervisor: não pode decidir aprovações."}` e `HTTP 403`.
- **Plano B:** `.scratch/e2e/relatorio.json`, item "autoaprovação recusada pela API" (HTTP 403, mesma mensagem), ou o slide 6 do deck ("Ele não aprova a própria ação").

### 10. O agente analista abre o incidente (2:55 a 3:20) · App, painel "Agente analista"

- **Dizer:** "A mesma cobrança em dobro aparece em 12 pedidos sem estorno. Aqui o Gabriel segue o fio até a causa comum: o agente analista abre um incidente e avisa os clientes que aceitam contato antes de eles reclamarem."
- **Mostrar:** role até o painel **Agente analista**. No padrão `cobranca_em_dobro` (12 pedidos), clique em **Tratar**. Aparecem o número do incidente (`INC-…`), os avisos enviados e quem ficou sem aviso por falta de consentimento. No E2E das 10:59 foram 11 avisos e 1 cliente sem consentimento. O `INC-…` aparece também no **Console dos sistemas** e no **Canal do time**.
- **Plano B:** prints `.scratch/e2e/10-analista-resultado.png` e `11-analista-incidente.png`, ou `prototipo/prevencao.html`, em que o mesmo caminho passa por uma pessoa liberando o envio.

### 11. Placar e fechamento (3:20 a 3:50) · App, depois deck slides 9 e 10

- **Dizer:** "No placar está o que ele resolveu sozinho, o que esperou o cliente, o que esperou uma pessoa e o que escalou. E reexecutado sobre o histórico, o motor barrou 64 de 64 casos em que a soma no pedido passou do limite sem aprovação."
- **Mostrar:** o placar no topo do app, com **Valor executado** de R$ 118,80 depois da aprovação do passo 8. Depois, no deck, o slide 9 (64 de 64; R$ 1.356,91 de custo evitado estimado) e o slide 10 (próximos passos).
- **Plano B:** slide 9 direto.

## Se tudo falhar

Abra o slide 8 do deck, que já tem o vídeo da jornada embutido, ou `apresentacao/midia/demo.mp4` em tela cheia. Narre em cima dele, na ordem do vídeo: vigia, processar, reação adversa, aprovação, aguardando cliente, verificação de evidência e analista. Os passos 7 e 9 ficam com os próprios planos B, porque não aparecem no vídeo. O Slack também não aparece: diga que a mesma aprovação chega ao Slack com botões. Não leia os números do placar do vídeo: são os de antes do último ajuste (29 / 2 / 18 / 16).

## Conferência

- **Interface:** código de `web/src`:
  - **Avançar o relógio para 08:20** e **Rodar vigia** no Canal do time;
  - **Processar fila**;
  - **Verificar** na verificação de evidência;
  - **Tratar** no painel do agente analista;
  - seletor de supervisor sem quem pediu;
  - **Aguardando cliente** no placar.
- **Decisão da suspeita:**
  - a tela vem do teste `web/src/components/DecisaoSuspeita.test.tsx` (prazo visível, sem quem sinalizou no seletor, justificativa obrigatória, botões `btn-suspeita-procedente` e `btn-suspeita-improcedente`);
  - a regra vem de `POST /api/suspeitas/{id}/decidir`: 403 para quem não é supervisor ou para quem sinalizou;
  - o componente `DecisaoSuspeita.tsx` (rótulos "Supervisor que decide", "Justificativa da decisão", "Procedente" e "Improcedente") apareceu às 11:18, ligado à verificação de evidência e ao Canal do time. Não o vi rodando: foi conferido pelo código.
- **Slack:** código de `src/atendimento/canal_slack/`:
  - botões **Aprovar**, **Rejeitar**, **Procedente** e **Improcedente** só em mensagem pendente (`blocos.py`);
  - quem clica precisa estar em `SLACK_SUPERVISORES`; o clique chama a mesma aprovação do app, com a mesma regra de quem pode aprovar (`canal.py`, `ao_clicar`);
  - o `@Gabriel` responde status de pedido e registra `responder_colaborador`; pedido de colaborador com dinheiro passa pela política (HG-10);
  - "só o que pede ação, mais um resumo por rodada" é a mudança que o W2 está fazendo agora, informada pelo coordenador. Não vi o Slack rodando: o passo 8 foi conferido pelo código e pelo `.env.example`.
- **Leitor com Claude:** `ingestao/avaliacao_leitor_claude.md` (amostra de 300; 62,0% contra 53,7%; US$ 2,37 pela amostra) e `src/atendimento/agente/leitor.py` (`ATENDIMENTO_LLM=1`, cache em `var/cache_leitor_claude`). O US$ 0,50 por rodada é a mesma conta aplicada às 65 conversas da fila.
- **Números:**
  - placar atual (34 / 2 / 18 / 0 / 11, R$ 636,00), informado pelo coordenador às 11:16;
  - vigia e analista, de `.scratch/e2e/relatorio.json` (20 de 20 aprovados, 10:59);
  - a aprovação, a resposta neutra do replay e o HTTP 403, reproduzidos numa cópia da API em memória.
- **Servidor ao vivo:** só GET em `localhost:8000`. Nenhum clique em `localhost:5173`.
