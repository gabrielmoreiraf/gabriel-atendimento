# Roteiro da demo ao vivo do FIO (3 a 4 minutos)

O FIO é o colega de atendimento da Gocase e da GoBeauté. Ele segue o fio de cada pedido pelos sistemas e acha a causa comum dos contatos repetidos.

Três janelas, nesta ordem de abas no navegador:

1. **Deck:** `apresentacao/index.html` (setas para navegar; `#9` na URL abre o slide 9; tecla `N` mostra as notas com as fontes).
2. **Protótipo 360°:** `prototipo/index.html` (estático, abre sem servidor).
3. **App da PoC:** `http://localhost:5173` (interface React do W5), falando com a API do W4 em `http://localhost:8000`.

Deixe também um terminal pronto para os passos 7 e 9 e o vídeo `apresentacao/midia/demo.mp4` aberto e pausado no player, para o plano B. O vídeo é a jornada E2E das 10:59, com 20 de 20 verificações aprovadas. O placar dele é de antes do último ajuste do leitor (29 resolvidas e 16 escaladas): não leia esses números em voz alta.

## Antes de subir no palco (5 min antes)

- [ ] **Estado zerado.** O estado do FIO vive em memória, e os avisos do vigia só saem uma vez por execução da API. Às 11:18 a API estava zerada. Se alguém ensaiar depois disso, reinicie **sem `--reload`**, para que uma edição em `src/` não reinicie a API no meio da demo:
  ```bash
  uv run uvicorn atendimento.api.app:app --port 8000
  ```
- [ ] **A API responde?** `curl -s -m 5 localhost:8000/api/placar` deve trazer tudo zerado. Entre 10:49 e 10:53 ela travou e não respondia a GET.
- [ ] **Botões da suspeita na tela.** A decisão da suspeita (passo 7) chegou ao app às 11:18 e não estava no vídeo nem no E2E das 10:59. No ensaio, confira se, depois de **Verificar** o `AT104936`, aparecem **Procedente** e **Improcedente**. Se não aparecerem, use o plano B do passo 7.
- [ ] **Deck no slide 1**, protótipo no mapa, app recarregado com a fila visível e o relógio em 08:00.
- [ ] **Zoom do navegador em 125%** no app, para a banca ler de longe.
- [ ] **Terminal com os comandos dos passos 7 e 9 colados**, ainda não executados.

## Passo a passo

Os tempos são acumulados. O que está entre aspas é a frase para dizer.

### 1. A dor (0:00 a 0:15) · Deck, slides 1 e 2

- **Dizer:** "O Reclame Aqui tem 11,6% das conversas e metade do custo, e cada conversa toma 12 minutos de uma pessoa abrindo sistema por sistema."
- **Mostrar:** slide 1 (capa) → seta → slide 2 (custo por canal).
- **Plano B:** se o deck não abrir, fale a frase em cima do mapa do passo 2.

### 2. A visão 360° (0:15 a 0:30) · Protótipo, `index.html`

- **Dizer:** "O FIO cobre as cinco frentes do atendimento. Em amarelo está onde uma pessoa decide, e hoje vamos provar ao vivo a verificação da reclamação e a escalação."
- **Mostrar:** o mapa. Passe o cursor pela linha amarela "Pessoa decide" e pare nas colunas F3 e F4, com o selo "Provado na PoC".
- **Plano B:** slide 4 do deck ("Cinco frentes…").

### 3. A fila das 08h e o vigia das 08:20 (0:30 a 0:50) · App, fila e "Canal do time"

- **Dizer:** "São 8h de 02/11, com 65 conversas abertas. Sem ninguém perguntar, o FIO olha o relógio e avisa o time do que vai estourar o prazo."
- **Mostrar:** a fila à esquerda (65 itens) e o placar zerado. No **Canal do time**, clique em **Avançar o relógio para 08:20**. Chegam **19 avisos de SLA**: o e-mail `AT116480`, que já passou do prazo, e as conversas de WhatsApp perto de vencer. Cada aviso diz o impacto e de quem o FIO espera ação.
- **Plano B:** prints `.scratch/e2e/01-inicio.png` e `02-vigia-canal.png`.

### 4. Processar fila (0:50 a 1:15) · App

- **Dizer:** "Um clique, e ele trata cada conversa: consulta o pedido, abre chamado na transportadora, responde o cliente e registra tudo no log. Quando falta foto, ele pede e espera, sem contar como resolvido."
- **Mostrar:**
  - botão **Processar fila** no placar;
  - o **Console dos sistemas** enchendo de ações;
  - o placar, que deve chegar a **34 resolvidas sozinho, 2 aguardando aprovação, 18 aguardando cliente, 0 suspeitas e 11 escaladas**, com **R$ 636,00** de custo evitado;
  - se der tempo, `AT116666`, em que ele pediu foto do produto e da embalagem.
- **Plano B:** print `.scratch/e2e/03-fila-processada.png` (e `08-aguardando-cliente.png` para os pedidos de foto), ou `demo.mp4` a partir do início. O placar dos prints e do vídeo é o antigo.

### 5. Reação adversa escalada (1:15 a 1:35) · App, conversa `AT116568`

- **Dizer:** "Aqui ele não resolve sozinho: a cliente teve reação ao produto. Ele orienta a suspender o uso e passa o caso ao supervisor, que registra a cosmetovigilância."
- **Mostrar:** clique em `AT116568` na fila. No painel do caso:
  - estado **escalada**;
  - **Decisão da política** = Escalar, pela regra `categorias.reacao_adversa.acoes_obrigatorias`;
  - **Resposta enviada ao cliente:** manda suspender o uso e diz que uma pessoa fala com ela em até 24 h.
- **Plano B:** print `.scratch/e2e/04-caso-reacao-adversa.png`.

### 6. Verificação de evidência no histórico (1:35 a 2:00) · App, seção "Verificação de evidência"

- **Dizer:** "Agora a frente de fraude, rodando sobre uma reclamação antiga, no dia em que ela chegou. A foto foi tirada antes de o pedido ser entregue e já tinha aparecido em outro pedido. O FIO segura o reenvio, manda para o supervisor, e o cliente recebe só uma resposta neutra."
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
  - Se escolher **Procedente**, o FIO segue a política do caso: executa o reenvio ou pede aprovação, somando o que o pedido já recebeu.
  - Os botões só liberam depois de escrita a justificativa.
- **Plano B:** sem os botões na tela, mostre a regra pela API. Este comando pega a suspeita pendente e tenta decidi-la como `agente`, quem a sinalizou:
  ```bash
  SUS=$(curl -s localhost:8000/api/suspeitas | jq -r '.[0].suspeita_id')
  curl -s -w '\nHTTP %{http_code}\n' -X POST localhost:8000/api/suspeitas/$SUS/decidir \
    -H 'content-type: application/json' \
    -d '{"supervisor_id":"agente","decisao":"improcedente","justificativa":"teste"}'
  ```
  Saída esperada: HTTP 403, porque só o supervisor decide (`reclamacao_suspeita.quem_decide`). Sem terminal, cite o slide 5 e siga.

### 8. Aprovação por outro supervisor (2:20 a 2:40) · App, "Canal do time" e "Console dos sistemas"

- **Dizer:** "Cobrança em dobro de R$ 118,80. O limite dele para reembolso é R$ 100, então ele pede aprovação no canal do time, e quem aprova é um supervisor, não ele."
- **Mostrar:**
  - no **Canal do time**, o pedido de aprovação de `AT116677` (reembolsar R$ 118,80, pedido `GBH491723`, endereçado à supervisora do turno);
  - no campo **Supervisor**, escolha **Roberto Mendes**, um supervisor diferente; escreva um comentário curto e clique em **Aprovar**;
  - a mensagem passa a mostrar o pedido como aprovado, e o **Console dos sistemas** mostra o `reembolsar` com o aprovador.
- **Plano B:** prints `.scratch/e2e/05-canal-pedido-aprovacao.png`, `06-aprovando.png` e `07-acao-aprovada-console.png`, nesta ordem. No vídeo e nos prints, o pedido aprovado é o outro pendente, `AT116520` (reembolso de R$ 155,81, por arrependimento).

### 9. Autoaprovação recusada (2:40 a 2:50) · Terminal

- **Dizer:** "A tela nem oferece quem pediu como aprovador. E se alguém tentar direto na API, o FIO não consegue aprovar o próprio pedido."
- **Mostrar:** rode o comando já colado. Ele pega o pedido de aprovação ainda pendente (o reembolso de `AT116520`) e tenta aprovar como `agente`:
  ```bash
  APR=$(curl -s localhost:8000/api/canal | jq -r '[.[] | select(.tipo=="aprovacao" and .estado=="pendente")][0].aprovacao_id')
  curl -s -w '\nHTTP %{http_code}\n' -X POST localhost:8000/api/aprovacoes/$APR/aprovar \
    -H 'content-type: application/json' -d '{"supervisor_id":"agente"}'
  ```
  Saída esperada: `{"detail":"agente não é supervisor: não pode decidir aprovações."}` e `HTTP 403`.
- **Plano B:** `.scratch/e2e/relatorio.json`, item "autoaprovação recusada pela API" (HTTP 403, mesma mensagem), ou o slide 6 do deck ("Ele não aprova a própria ação").

### 10. O agente analista abre o incidente (2:50 a 3:15) · App, painel "Agente analista"

- **Dizer:** "A mesma cobrança em dobro aparece em 12 pedidos sem estorno. Aqui o FIO segue o fio até a causa comum: o agente analista abre um incidente e avisa os clientes que aceitam contato antes de eles reclamarem."
- **Mostrar:** role até o painel **Agente analista**. No padrão `cobranca_em_dobro` (12 pedidos), clique em **Tratar**. Aparecem o número do incidente (`INC-…`), os avisos enviados e quem ficou sem aviso por falta de consentimento. No E2E das 10:59 foram 11 avisos e 1 cliente sem consentimento. O `INC-…` aparece também no **Console dos sistemas** e no **Canal do time**.
- **Plano B:** prints `.scratch/e2e/10-analista-resultado.png` e `11-analista-incidente.png`, ou `prototipo/prevencao.html`, em que o mesmo caminho passa por uma pessoa liberando o envio.

### 11. Placar e fechamento (3:15 a 3:45) · App, depois deck slides 9 e 10

- **Dizer:** "No placar está o que ele resolveu sozinho, o que esperou o cliente, o que esperou uma pessoa e o que escalou. E reexecutado sobre o histórico, o motor barrou 64 de 64 casos em que a soma no pedido passou do limite sem aprovação."
- **Mostrar:** o placar no topo do app, com **Valor executado** de R$ 118,80 depois da aprovação do passo 8. Depois, no deck, o slide 9 (64 de 64; R$ 1.356,91 de custo evitado estimado) e o slide 10 (próximos passos).
- **Plano B:** slide 9 direto.

## Se tudo falhar

Abra o slide 8 do deck, que já tem o vídeo da jornada embutido, ou `apresentacao/midia/demo.mp4` em tela cheia. Narre em cima dele, na ordem do vídeo: vigia, processar, reação adversa, aprovação, aguardando cliente, verificação de evidência e analista. Os passos 7 e 9 ficam com os próprios planos B, porque não aparecem no vídeo. Não leia os números do placar do vídeo: são os de antes do último ajuste (29 / 2 / 18 / 16).

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
- **Números:**
  - placar atual (34 / 2 / 18 / 0 / 11, R$ 636,00), informado pelo coordenador às 11:16;
  - vigia e analista, de `.scratch/e2e/relatorio.json` (20 de 20 aprovados, 10:59);
  - a aprovação, a resposta neutra do replay e o HTTP 403, reproduzidos numa cópia da API em memória.
- **Servidor ao vivo:** só GET em `localhost:8000`. Nenhum clique em `localhost:5173`.
