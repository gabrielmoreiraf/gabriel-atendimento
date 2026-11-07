/* Protótipo da Mesa do colega. Só estado de tela: nenhuma regra de negócio mora aqui (ADR-001). */
(() => {
  "use strict";

  // ---------- Vocabulário ----------
  const CANAL = { whatsapp: "WhatsApp", email: "E-mail", reclame_aqui: "Reclame Aqui" };
  const ESTADO = {
    aberta: "Aberta", resolvida: "Resolvida", aguardando_aprovacao: "Aguardando aprovação",
    suspeita: "Suspeita", escalada: "Escalada",
  };
  const PESSOA = {
    supervisor_01: "Paula G.", supervisor_02: "Roberto M.", supervisor_03: "Cristiane L.",
    agente: "Colega", analista_01: "Marcelo T.",
  };
  const CATEGORIA = {
    atraso: "atraso na entrega", rastreio: "rastreio", item_faltante: "item faltante",
    avaria_vazamento: "avaria ou vazamento", arrependimento: "arrependimento",
    erro_personalizacao: "erro de personalização", reacao_adversa: "reação adversa",
    cobranca_duplicada: "cobrança duplicada", outros: "outros",
  };
  const ACAO = {
    classificar_conversa: ["Classificou a conversa", "i-etiqueta"],
    responder_cliente: ["Respondeu ao cliente", "i-balao"],
    informar_status: ["Mandou o status do rastreio", "i-caminhao"],
    abrir_chamado_transportadora: ["Abriu chamado na transportadora", "i-caminhao"],
    solicitar_foto: ["Pediu foto do produto e da embalagem", "i-imagem"],
    acionar_pessoa: ["Chamou uma pessoa no canal do time", "i-boia"],
    encerrar_conversa: ["Encerrou a conversa", "i-ok"],
    solicitar_aprovacao: ["Pediu aprovação no canal do time", "i-pessoa"],
    aprovar_acao: ["Aprovação registrada", "i-ok"],
    reembolsar: ["Reembolsou", "i-cartao"],
    negar_por_politica: ["Negou por política", "i-lei"],
    orientar_suspensao_uso: ["Orientou a suspensão do uso", "i-escudo"],
    registrar_cosmetovigilancia: ["Registrou cosmetovigilância", "i-escudo"],
    sinalizar_suspeita: ["Sinalizou suspeita ao supervisor", "i-escudo"],
    reenviar_produto: ["Reenviou o produto", "i-caminhao"],
  };
  const ENTREGA = { entregue: "Entregue", em_transito: "Em trânsito", aguardando_separacao: "Aguardando separação" };
  const PAGTO = { cartao_credito: "Cartão de crédito", boleto: "Boleto", pix: "Pix" };

  const $ = (s, r = document) => r.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const ico = (id, cls = "ico") => `<svg class="${cls}" aria-hidden="true"><use href="#${id}"/></svg>`;
  const rs = (v) => "R$ " + v.toFixed(2).replace(".", ",").replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const dataCurta = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}${s.length > 10 ? " " + s.slice(11, 16) : ""}` : "—");
  const reduzir = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---------- Dados ----------
  const casos = window.FILA.map((c) => ({ ...c, grupo: "fila" }));
  const porId = Object.fromEntries(casos.map((c) => [c.id, c]));

  // AT116677: na rodada real a aprovação veio da jornada E2E. Aqui ela fica pendente para o supervisor decidir.
  {
    const c = porId.AT116677;
    const i = c.acoes.findIndex((a) => a.acao === "aprovar_acao");
    c.aposAprovar = c.acoes.slice(i);
    c.acoes = c.acoes.slice(0, i);
    c.estado = "aguardando_aprovacao";
  }

  // Replay do histórico: a fila das 08h não tem foto suspeita; esta conversa de 02/10 tem.
  casos.push({
    id: "AT112299", grupo: "replay", canal: "whatsapp", marca: "Gocase", assunto: "Capinha com rachadura na borda",
    pedido: "GCH544744", abertura: "2026-10-02 11:44:06", categoria: "avaria_vazamento", estado: "suspeita",
    mensagens: [
      { autor: "bot", ts: "2026-10-02 11:44:06", texto: "Olá! Sou a Gi, assistente virtual da Gocase 💜 Como posso te ajudar hoje?" },
      { autor: "cliente", ts: "2026-10-02 11:44:31", texto: "A borda da capinha do iPhone 16 Pro veio com uma rachadura" },
      { autor: "cliente", ts: "2026-10-02 11:46:51", texto: "Nem consegui usar. Quero o reenvio." },
      { autor: "cliente", ts: "2026-10-02 12:11:46", texto: "segue a foto [imagem]" },
    ],
    acoes: [
      { id: "R1", sistema: "Central de atendimento", acao: "classificar_conversa", valor: 0, por: "agente", aprovado: null, ref: "CLS-AT112299" },
      { id: "R2", sistema: "Canal do time", acao: "sinalizar_suspeita", valor: 0, por: "agente", aprovado: null, ref: "SUS-PROTO-01" },
      { id: "R3", sistema: "Central de atendimento", acao: "responder_cliente", valor: 0, por: "agente", aprovado: null, ref: "MSG-PROTO-01",
        texto: "Recebemos sua foto, obrigado. Um especialista vai analisar o seu caso e te responde por aqui em até 24 horas." },
    ],
    pedidoInfo: { order_id: "GCH544744", valor: "132.80", descricao_produto: "Case Guard Magsafe / iPhone 16 Pro Personalizada Iniciais", transportadora: "Rápido Sul", uf: "RJ", status_entrega: "entregue", data_entrega: "2026-09-25", data_prometida: "2026-09-28", lote_produto: "", forma_pagamento: "cartao_credito" },
  });
  porId.AT112299 = casos[casos.length - 1];

  // O que cada caso destacado mostra além do registro bruto (decisão, alçada, evidência).
  const ENRIQ = {
    AT116520: {
      desfecho: ["Reembolso de R$ 155,81 esperando aprovação", "Passa do limite de R$ 100,00 do atendente. O colega pediu a Paula G. no canal do time e avisou a cliente que a solução está encaminhada."],
      decisao: { titulo: "Devolução por arrependimento cabe no prazo", texto: "Entregue em 26/10, contato em 31/10: dia 5 de 7 após o recebimento (CDC, art. 49). O reembolso integral é de R$ 155,81, acima da alçada do atendente.", regra: "limites_por_papel.atendente.reembolso_max_rs", alcada: { valor: 155.81, acumulado: 0, limite: 100 } },
    },
    AT116677: {
      desfecho: ["Estorno de R$ 118,80 esperando aprovação", "O gateway mostra o boleto pago e o cartão capturado no mesmo pedido. O estorno passa do limite de R$ 100,00 e foi pedido a Paula G."],
      decisao: { titulo: "Cobrança em dobro confirmada no gateway", texto: "TRX00005946 · boleto · R$ 118,80 · paga em 01/11. TRX00005947 · cartão final 9879 · R$ 118,80 · capturada em 31/10. Nenhum estorno anterior no pedido.", regra: "limites_por_papel.atendente.reembolso_max_rs", alcada: { valor: 118.8, acumulado: 0, limite: 100 } },
    },
    AT116568: {
      desfecho: ["Reação adversa: com a supervisão", "O colega orientou a cliente a suspender o uso e chamou Paula G. para registrar a cosmetovigilância do lote LT2609-D. Trocar o produto não substitui o registro."],
      decisao: { titulo: "Caso sensível: não troca sem registro", texto: "Relato de rosto inchado após o uso do Greens Superfood. A política manda orientar a suspensão e acionar a supervisão; a troca pedida pela cliente fica para depois do registro.", regra: "categorias.reacao_adversa.acionar = supervisor" },
    },
    AT116473: {
      desfecho: ["Resolvido pelo colega", "Pedido parado em 'aguardando transferência' desde 29/10. Chamado aberto no Portal Expressa Já e status enviado à cliente. É a 2ª vez que ela escreve sobre este pedido."],
    },
    AT116524: {
      desfecho: ["Esperando a foto da cliente", "Para erro de personalização a política pede foto antes de decidir. O colega pediu e retoma o caso quando a foto chegar."],
    },
    AT112299: {
      desfecho: ["A foto não fecha com o pedido", "Dois sinais fortes: a mesma imagem já veio em outro pedido e a foto foi tirada antes da entrega. O colega não acusou o cliente: respondeu de forma neutra e passou a decisão à supervisão."],
      evidencia: true,
    },
  };

  // Aprovações e decisões pendentes, como o canal do time as mostra.
  const aprovacoes = {
    "APR-000001": { id: "APR-000001", caso: "AT116677", titulo: "Estorno de R$ 118,80", valor: 118.8, motivo: "Cobrança em dobro (boleto + cartão)", para: "supervisor_01", estado: "pendente" },
    "APR-000002": { id: "APR-000002", caso: "AT116520", titulo: "Reembolso de R$ 155,81", valor: 155.81, motivo: "Arrependimento, dia 5 de 7 (CDC, art. 49)", para: "supervisor_01", estado: "pendente" },
  };
  const outrasDecisoes = { cosmeto: "pendente", suspeita: "pendente" };

  // ---------- Estado da tela ----------
  const ui = {
    processado: false, selecionado: "AT116520", canal: "todos", estado: null, busca: "",
    escopo: "caso", quem: "supervisor_01", marcarRef: null, abertos: {}, extraConsole: [], posts: [], novos: new Set(),
  };

  const estadoDe = (c) => (ui.processado || c.grupo === "replay" ? c.estado : "aberta");
  const visiveis = () => casos.filter((c) => c.grupo === "replay" ? ui.processado : true);
  const filaDe = () => casos.filter((c) => c.grupo === "fila");

  function resumoAcao(c) {
    if (!ui.processado && c.grupo === "fila") {
      const semResposta = c.canal === "whatsapp" && !c.mensagens.some((m) => m.autor === "agente");
      return semResposta ? `<span class="item-sla">Sem resposta humana · SLA estoura 08:30</span>` : esc(c.mensagens.filter((m) => m.autor === "cliente").at(-1)?.texto || "");
    }
    const ord = ["reembolsar", "sinalizar_suspeita", "abrir_chamado_transportadora", "solicitar_aprovacao", "orientar_suspensao_uso", "acionar_pessoa", "solicitar_foto", "negar_por_politica", "informar_status", "encerrar_conversa", "responder_cliente"];
    for (const nome of ord) {
      const a = c.acoes.find((x) => x.acao === nome);
      if (!a) continue;
      const base = ACAO[nome][0];
      if (nome === "abrir_chamado_transportadora") return `${base}: ${esc(a.ref)}`;
      if (nome === "reembolsar") return `${base} ${rs(a.valor)} · ${esc(a.ref)}`;
      if (nome === "solicitar_aprovacao") return `Pediu aprovação: ${rs(a.valor)} acima da alçada`;
      if (nome === "acionar_pessoa" && c.categoria === "outros") return "Sem regra automática: chamou uma pessoa";
      return base;
    }
    return "Ainda sem ação";
  }

  // ---------- Placar ----------
  function contagem() {
    const q = { resolvida: 0, aberta: 0, aguardando_aprovacao: 0, suspeita: 0, escalada: 0 };
    visiveis().forEach((c) => q[estadoDe(c)]++);
    const valor = [...casos.flatMap((c) => c.acoes), ...ui.extraConsole].filter((a) => a.acao === "reembolsar").reduce((s, a) => s + a.valor, 0);
    return { q, valor };
  }

  function renderPlacar() {
    const el = $("#placar");
    if (!ui.processado) {
      const f = filaDe();
      const n = (k) => f.filter((c) => c.canal === k).length;
      const sla = f.filter((c) => c.canal === "whatsapp" && !c.mensagens.some((m) => m.autor === "agente")).length;
      el.innerHTML = `
        <div class="placar-antes">
          <span><b>${f.length}</b> conversas abertas</span>
          <span style="font-size:var(--text-sm);color:var(--color-text-muted)">${n("whatsapp")} WhatsApp · ${n("email")} e-mail · ${n("reclame_aqui")} Reclame Aqui</span>
          <span class="alerta-sla">${ico("i-relogio")}${sla} no WhatsApp estouram o SLA de 30 min às 08:30</span>
        </div>
        <div class="placar-acao">
          <p>O colega lê cada conversa, confere pedido e política e age nos sistemas.</p>
          <button class="btn btn-pri" id="processar" type="button">${ico("i-play")}Processar a fila</button>
        </div>`;
      $("#processar").onclick = processar;
    } else {
      const { q, valor } = contagem();
      const bt = (k, rotulo, sub) => `
        <button type="button" class="placar-num e-${k}" data-estado="${k}" aria-pressed="${ui.estado === k}">
          <b>${q[k]}</b><span>${rotulo}</span><small>${sub}</small>
        </button>`;
      el.innerHTML = `
        ${bt("resolvida", "Resolvidas sozinho", "ação registrada")}
        ${bt("aberta", "Esperando o cliente", "foto ou dado")}
        ${bt("aguardando_aprovacao", "Esperando aprovação", "acima da alçada")}
        ${bt("suspeita", "Suspeitas", "supervisão decide")}
        ${bt("escalada", "Com uma pessoa", "sensível ou sem regra")}
        <span class="placar-sep" aria-hidden="true"></span>
        <div class="placar-num valor"><b>${rs(valor)}</b><span>Executado em dinheiro</span><small>na alçada ou aprovado</small></div>
`;
      el.querySelectorAll("[data-estado]").forEach((b) => (b.onclick = () => {
        ui.estado = ui.estado === b.dataset.estado ? null : b.dataset.estado;
        render();
      }));
    }
    document.documentElement.style.setProperty("--placar-h", el.offsetHeight + "px");
  }

  // ---------- Fila ----------
  function filtrados() {
    const t = ui.busca.trim().toLowerCase();
    return visiveis().filter((c) =>
      (ui.canal === "todos" || c.canal === ui.canal) &&
      (!ui.estado || estadoDe(c) === ui.estado) &&
      (!t || [c.id, c.pedido, c.marca, c.assunto].some((v) => (v || "").toLowerCase().includes(t))));
  }

  function renderCanais() {
    const base = filaDe();
    const n = (k) => base.filter((c) => k === "todos" || c.canal === k).length;
    $("#canais").innerHTML = ["todos", "whatsapp", "email", "reclame_aqui"].map((k) => `
      <button type="button" data-canal="${k}" aria-pressed="${ui.canal === k}" title="${k === "todos" ? "Todos os canais" : CANAL[k]}">
        ${k === "todos" ? "Todos" : k === "reclame_aqui" ? '<abbr title="Reclame Aqui" style="text-decoration:none">RA</abbr>' : CANAL[k]}
        <span class="mono">${n(k)}</span></button>`).join("");
    $("#canais").querySelectorAll("button").forEach((b) => (b.onclick = () => { ui.canal = b.dataset.canal; render(); }));
  }

  function itemHTML(c) {
    const e = estadoDe(c);
    return `<li><button type="button" class="item${ui.novos.has(c.id) ? " novo" : ""}" data-id="${c.id}" aria-current="${ui.selecionado === c.id}">
      <span class="item-id">${ico("i-" + c.canal)}${c.id} · ${esc(c.marca)}</span>
      <span class="selo e-${e}">${ESTADO[e]}</span>
      <span class="item-assunto">${esc(c.assunto || (c.categoria ? CATEGORIA[c.categoria] : "Sem assunto"))}</span>
      <span class="item-feito">${resumoAcao(c)}</span>
    </button></li>`;
  }

  function renderFila() {
    const lista = filtrados();
    $("#fila-total").textContent = `${filaDe().length} conversas`;
    const fa = $("#filtro-ativo");
    if (ui.estado) {
      fa.hidden = false;
      fa.innerHTML = `<span>Mostrando: <strong>${ESTADO[ui.estado]}</strong> (${lista.length})</span><button class="btn-link btn" type="button" id="limpar">Limpar filtro</button>`;
      $("#limpar").onclick = () => { ui.estado = null; render(); };
    } else fa.hidden = true;
    const fila = lista.filter((c) => c.grupo === "fila");
    const replay = lista.filter((c) => c.grupo === "replay");
    $("#lista").innerHTML = (fila.map(itemHTML).join("") || `<li class="lista-vazia">Nenhuma conversa com esse filtro.</li>`) +
      (replay.length ? `<li class="lista-grupo">Replay do histórico · fotos</li>${replay.map(itemHTML).join("")}` : "");
    $("#lista").querySelectorAll(".item").forEach((b) => (b.onclick = () => selecionar(b.dataset.id)));
  }

  // ---------- Caso ----------
  function pedidoHTML(c) {
    const p = c.pedidoInfo;
    if (!p) return `<dl class="pedido"><div class="largo"><dt>Pedido</dt><dd>Sem pedido identificado na conversa. Ação com dinheiro vira escalação (Q20).</dd></div></dl>`;
    return `<dl class="pedido">
      <div class="largo"><dt>Produto</dt><dd>${esc(p.descricao_produto)}</dd></div>
      <div><dt>Valor</dt><dd class="mono">${rs(Number(p.valor))}</dd></div>
      <div><dt>Pagamento</dt><dd>${PAGTO[p.forma_pagamento] || esc(p.forma_pagamento)}</dd></div>
      <div><dt>Entrega</dt><dd>${ENTREGA[p.status_entrega] || esc(p.status_entrega)}${p.data_entrega ? ` <span class="mono">${dataCurta(p.data_entrega)}</span>` : ""}</dd></div>
      <div><dt>Prometida para</dt><dd class="mono">${dataCurta(p.data_prometida)}</dd></div>
      <div><dt>Transportadora</dt><dd>${esc(p.transportadora)} · ${esc(p.uf)}</dd></div>
      <div><dt>Lote</dt><dd class="mono">${esc(p.lote_produto || "—")}</dd></div>
    </dl>`;
  }

  function mensagemHTML(m) {
    if (m.autor === "bot") return `<li class="msg bot"><div class="msg-autor">Assistente automático · <span class="mono">${dataCurta(m.ts)}</span></div><div class="msg-texto">${esc(m.texto)}</div></li>`;
    if (m.autor === "agente") return `<li class="msg saida humano"><div class="msg-autor">Atendente do time · <span class="mono">${dataCurta(m.ts)}</span></div><div class="msg-texto">${esc(m.texto)}</div></li>`;
    return `<li class="msg"><div class="msg-autor">Cliente · <span class="mono">${dataCurta(m.ts)}</span></div><div class="msg-texto">${esc(m.texto)}</div></li>`;
  }

  function desfechoGenerico(c) {
    const e = estadoDe(c);
    if (e === "aberta") return ["Esperando o cliente", "O colega pediu o que faltava para decidir e retoma quando o cliente responder."];
    if (e === "escalada") return c.categoria === "outros" || !c.categoria
      ? ["Com uma pessoa do time", "Demanda sem regra automática no MVP. O colega avisou a supervisão no canal do time e não respondeu nada que não pudesse cumprir."]
      : ["Com uma pessoa do time", "O colega chamou a pessoa certa no canal do time."];
    if (c.acoes.some((a) => a.acao === "encerrar_conversa")) return ["Encerrada pelo colega", "Só o assistente automático tinha falado e o cliente não voltou. Nada a fazer nos sistemas."];
    return ["Resolvido pelo colega", "Ação feita no sistema e resposta enviada ao cliente. Tudo registrado no console."];
  }

  const ICO_ESTADO = { resolvida: "i-ok", aberta: "i-relogio", aguardando_aprovacao: "i-pessoa", suspeita: "i-escudo", escalada: "i-boia" };

  function desfechoHTML(c) {
    const e = estadoDe(c);
    const pend = Object.values(aprovacoes).find((a) => a.caso === c.id);
    let [t, x] = (ENRIQ[c.id] && ENRIQ[c.id].desfecho) || desfechoGenerico(c);
    if (pend && pend.estado === "aprovada") [t, x] = [`${pend.titulo.split(" de ")[0]} feito após aprovação`, `${PESSOA[pend.decidido]} aprovou às 08:24. O colega executou no Gateway de pagamentos e avisou a cliente.`];
    if (pend && pend.estado === "rejeitada") [t, x] = ["Aprovação recusada: com uma pessoa", `${PESSOA[pend.decidido]} recusou: "${pend.justificativa}". O colega não executou nada e devolveu o caso ao time.`];
    if (c.id === "AT112299" && outrasDecisoes.suspeita !== "pendente") [t, x] = outrasDecisoes.suspeita === "aceita"
      ? ["Supervisão aceitou a reclamação", "O reenvio de R$ 132,80 cabe na alçada e foi feito pelo colega."]
      : ["Supervisão manteve a suspeita", "O colega pede nova foto ao cliente, sem acusação, e não reenvia por enquanto."];
    const irCanal = (pend && pend.estado === "pendente") || (c.id === "AT112299" && outrasDecisoes.suspeita === "pendente") || (c.id === "AT116568" && outrasDecisoes.cosmeto === "pendente");
    return `<div class="desfecho e-${e}">${ico(ICO_ESTADO[e])}<div><h2>${esc(t)}</h2><p>${esc(x)}</p></div>
      ${irCanal ? `<button class="btn" type="button" data-ir-canal="${c.id}">Ver no canal do time</button>` : ""}</div>`;
  }

  function decisaoHTML(d) {
    if (!d) return "";
    let alc = "";
    if (d.alcada) {
      const { valor, acumulado, limite } = d.alcada;
      const total = acumulado + valor, escala = Math.max(total, limite) * 1.15;
      alc = `<div class="alcada" role="img" aria-label="Alçada: ${rs(total)} no pedido contra limite de ${rs(limite)}">
        <div class="alcada-barra"><i class="${total <= limite ? "ok" : ""}" style="width:${(total / escala) * 100}%"></i><em style="left:${(limite / escala) * 100}%"></em></div>
        <div class="alcada-legenda"><span>No pedido: <b>${rs(total)}</b> (já executado antes: ${rs(acumulado)})</span><span>Limite do atendente: <b>${rs(limite)}</b></span></div>
      </div>`;
    }
    return `<li class="cartao"><h3>${ico("i-lei")}${esc(d.titulo)}</h3><p>${esc(d.texto)}</p><span class="regra">${esc(d.regra)}</span>${alc}</li>`;
  }

  function evidenciaHTML() {
    // Linha do tempo: captura 04/09 → entrega 25/09 → envio 02/10. Geometria, não ilustração.
    const x = (d) => 40 + ((d - 0) / 28) * 560; // dia 0 = 04/09, dia 28 = 02/10
    return `<li class="cartao"><h3>${ico("i-escudo")}Verificação da foto</h3>
      <div class="anexo"><div class="anexo-foto">${ico("i-imagem")}</div>
        <p><span class="mono">IMG000209</span> · Redmi 13C · sem editor<br><span style="color:var(--color-text-muted)">Capinha transparente com estampa rachada na lateral, perto dos botões.</span></p></div>
      <ul class="sinais">
        <li class="sinal"><span class="forca forte">Forte</span><span><b>Imagem repetida.</b> Mesmo hash perceptual <span class="mono">237d1e1449ffb0e4</span> enviado em AT108528, pedido <span class="mono">GCH535004</span>, de outro cliente, um mês antes.</span></li>
        <li class="sinal"><span class="forca forte">Forte</span><span><b>Foto antes da entrega.</b> Capturada em 04/09; o pedido foi entregue em 25/09.</span></li>
        <li class="sinal"><span class="forca contexto">Contexto</span><span>Personalização "iniciais" não aparece na descrição da foto. Sozinho, não faria do caso uma suspeita.</span></li>
      </ul>
      <svg class="linha-tempo" viewBox="0 0 640 70" role="img" aria-label="Captura em 04/09, entrega em 25/09, envio da foto em 02/10">
        <line x1="40" x2="600" y1="30" y2="30" stroke="var(--color-border-strong)" stroke-width="2"/>
        <circle cx="${x(0)}" cy="30" r="7" fill="var(--color-suspeita)"/>
        <circle cx="${x(21)}" cy="30" r="7" fill="var(--color-surface)" stroke="var(--color-text)" stroke-width="2"/>
        <circle cx="${x(28)}" cy="30" r="7" fill="var(--color-text)"/>
        <text x="${x(0)}" y="60" text-anchor="start"><tspan class="dt">04/09</tspan> foto tirada</text>
        <text x="${x(21)}" y="60" text-anchor="middle"><tspan class="dt">25/09</tspan> entregue</text>
        <text x="${x(28)}" y="12" text-anchor="end"><tspan class="dt">02/10</tspan> enviada</text>
      </svg>
      <div class="custos">
        <div>Custo de aceitar se for falsa<b>${rs(132.8 * 0.45)}</b>45% do pedido de ${rs(132.8)}</div>
        <div>Custo de sinalizar se for verdadeira<b>${rs(6)}</b>tempo de análise da supervisão</div>
      </div>
      <span class="regra">Q15: sinal forte + custo de aceitar o falso maior que o de sinalizar → suspeita</span>
    </li>`;
  }

  function passosHTML(c) {
    const acoes = [...c.acoes, ...ui.extraConsole.filter((a) => a.conversa === c.id)];
    if (!acoes.length) return "";
    const sistemas = new Set(acoes.map((a) => a.sistema));
    const aberto = ui.abertos[c.id] !== false;
    const linhas = acoes.map((a) => {
      const [nome, icone] = ACAO[a.acao] || [a.acao, "i-agente"];
      let det = a.sistema;
      if (a.acao === "classificar_conversa" && c.categoria) det = `Categoria: ${CATEGORIA[c.categoria] || c.categoria}`;
      if (a.valor) det += ` · ${rs(a.valor)}`;
      if (a.aprovado) det += ` · aprovado por ${PESSOA[a.aprovado] || a.aprovado}`;
      if (a.por && a.por !== "agente") det += ` · feito por ${PESSOA[a.por] || a.por}`;
      return `<li class="passo"><span class="passo-ico">${ico(icone)}</span>
        <span class="passo-txt">${esc(nome)}<small>${esc(det)}</small></span>
        <button type="button" class="ref" data-ref="${esc(a.ref)}" title="Ver no console">${esc(a.ref)}</button></li>`;
    }).join("");
    return `<li><details class="passos" data-passos="${c.id}" ${aberto ? "open" : ""}>
      <summary><span class="agente-marca">${ico("i-agente")}</span>O colega trabalhou neste caso <small>· ${acoes.length} passos em ${sistemas.size} ${sistemas.size > 1 ? "sistemas" : "sistema"}</small>${ico("i-seta", "ico seta")}</summary>
      <ol>${linhas}</ol></details></li>`;
  }

  function respostasHTML(c) {
    const acoes = [...c.acoes, ...ui.extraConsole.filter((a) => a.conversa === c.id)];
    return acoes.filter((a) => a.acao === "responder_cliente" && a.texto).map((a) =>
      `<li class="msg saida"><div class="msg-autor"><span class="agente-marca" style="width:20px;height:20px;border-radius:6px">${ico("i-agente")}</span>Colega → cliente · <span class="mono">${a.hora || "02/11 08:00"}</span></div><div class="msg-texto">${esc(a.texto)}</div></li>`).join("");
  }

  function renderCaso() {
    const c = porId[ui.selecionado];
    const el = $("#caso");
    if (!c) { el.innerHTML = `<div class="vazio-caso"><b>Escolha uma conversa na fila</b></div>`; return; }
    const e = estadoDe(c);
    const en = ENRIQ[c.id] || {};
    const trabalhou = ui.processado || c.grupo === "replay";
    el.innerHTML = `
      <div class="caso-cabeca">
        <div>
          <h1>${c.id}</h1>
          <div class="caso-meta">
            <span>${ico("i-" + c.canal)}${CANAL[c.canal]}</span>
            <span>${esc(c.marca)}</span>
            <span>Aberta <span class="mono">${dataCurta(c.abertura)}</span></span>
            ${c.pedido ? `<span>Pedido <span class="mono">${c.pedido}</span></span>` : ""}
            ${c.grupo === "replay" ? `<span>Replay de uma conversa de outubro</span>` : ""}
          </div>
        </div>
        <span class="selo selo-grande e-${e}">${ESTADO[e]}</span>
      </div>
      ${trabalhou ? desfechoHTML(c) : ""}
      ${pedidoHTML(c)}
      <ol class="trilha">
        ${c.mensagens.map(mensagemHTML).join("")}
        ${trabalhou ? `${en.evidencia ? evidenciaHTML() : ""}${decisaoHTML(en.decisao)}${passosHTML(c)}${respostasHTML(c)}` :
          `<li class="vazio-caso"><b>O colega ainda não leu esta conversa</b><span>Ao processar a fila ele confere o pedido e a política, age nos sistemas e responde.</span><button class="btn btn-pri" type="button" id="processar2">${ico("i-play")}Processar a fila</button></li>`}
      </ol>`;
    const p2 = $("#processar2"); if (p2) p2.onclick = processar;
    el.querySelectorAll("[data-ref]").forEach((b) => (b.onclick = () => marcarNoConsole(b.dataset.ref)));
    el.querySelectorAll("[data-ir-canal]").forEach((b) => (b.onclick = () => irParaCanal(b.dataset.irCanal)));
    const d = el.querySelector("[data-passos]");
    if (d) d.addEventListener("toggle", () => (ui.abertos[c.id] = d.open));
  }

  // ---------- Console ----------
  function linhasConsole() {
    if (!ui.processado) return casos.filter((c) => c.grupo === "replay").flatMap((c) => c.acoes.map((a) => ({ ...a, conversa: c.id }))).filter(() => false);
    const base = casos.flatMap((c) => c.acoes.map((a) => ({ ...a, conversa: c.id, hora: c.grupo === "replay" ? "02/10 12:12" : "02/11 08:00" })));
    return [...base, ...ui.extraConsole];
  }

  function renderConsole() {
    const todas = linhasConsole();
    const linhas = ui.escopo === "caso" ? todas.filter((a) => a.conversa === ui.selecionado) : todas;
    const sistemas = new Set(todas.map((a) => a.sistema));
    $("#console-sub").textContent = ui.processado ? `${todas.length} registros em ${sistemas.size} sistemas` : "Nada executado ainda";
    $("#console").innerHTML = linhas.length ? linhas.slice().reverse().map((a) => `
      <tr class="${a.ref === ui.marcarRef ? "marcada" : ""}${a.novo ? " novo" : ""}" data-linha="${esc(a.ref)}">
        <td>${a.hora}</td><td>${a.conversa}</td><td>${esc(a.sistema)}</td><td>${esc(a.acao)}</td>
        <td class="num">${a.valor ? a.valor.toFixed(2).replace(".", ",") : ""}</td>
        <td>${esc(a.por === "agente" ? "agente" : a.por)}</td><td>${esc(a.aprovado || "")}</td><td>${esc(a.ref)}</td>
      </tr>`).join("") : `<tr><td colspan="8" class="vazio">${ui.processado ? "Nenhum registro deste caso." : "O console mostra cada ação que o colega faz nos sistemas, ao vivo."}</td></tr>`;
    document.querySelectorAll("[data-escopo]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.escopo === ui.escopo));
    ui.extraConsole.forEach((a) => (a.novo = false));
  }

  function marcarNoConsole(ref) {
    ui.marcarRef = ref; ui.escopo = "caso";
    renderConsole();
    const tr = document.querySelector(`[data-linha="${CSS.escape(ref)}"]`);
    if (tr) tr.scrollIntoView({ block: "nearest", behavior: reduzir ? "auto" : "smooth" });
  }

  // ---------- Canal do time ----------
  const ehSupervisor = () => ui.quem.startsWith("supervisor");

  function montarPosts() {
    const f = filaDe();
    const q = (e) => f.filter((c) => c.estado === e).length;
    const outros = f.filter((c) => c.estado === "escalada" && c.id !== "AT116568");
    const exj = f.flatMap((c) => c.acoes).filter((a) => a.sistema === "Portal Expressa Já").length;
    ui.posts = [
      { tipo: "resumo", hora: "08:00", html: `Bom dia, time. Peguei a fila das 08h: <b>${f.length} conversas</b>. Resolvi ${q("resolvida")} sozinho, ${q("aberta")} esperam foto ou dado do cliente, ${q("escalada")} precisam de alguém e ${q("aguardando_aprovacao")} reembolsos esperam aprovação. Todo WhatsApp respondido antes do SLA das 08:30.` },
      { tipo: "aprovacao", id: "APR-000001", hora: "08:00" },
      { tipo: "aprovacao", id: "APR-000002", hora: "08:00" },
      { tipo: "cosmeto", hora: "08:00" },
      { tipo: "grupo", hora: "08:00", ids: outros.map((c) => c.id) },
      { tipo: "aviso", hora: "08:01", html: `Abri <b>${exj} chamados</b> no Portal Expressa Já nesta fila, quase todos com "aguardando transferência". Passei para o <span class="mencao">agente analista</span> conferir se é um padrão antes de mais clientes escreverem.` },
      { tipo: "suspeita", hora: "08:02" },
    ];
  }

  const autorColega = (hora) => `<div class="post-autor">Colega <small>${hora}</small></div>`;

  function blocoAprovacao(a) {
    const c = porId[a.caso];
    let corpo;
    if (a.estado === "pendente") {
      if (!ehSupervisor()) corpo = `<p class="nota">Quem pediu não aprova a própria ação. Troque "Você é" para uma pessoa da supervisão.</p>
        <div class="acoes"><button class="btn btn-pri" disabled>Aprovar</button><button class="btn" disabled>Rejeitar</button></div>`;
      else if (ui.abertos[a.id] === "aprovar") corpo = `<label for="c-${a.id}">Comentário (opcional)</label><textarea id="c-${a.id}"></textarea>
        <div class="acoes"><button class="btn btn-pri" data-confirma="${a.id}">${ico("i-ok")}Confirmar ${esc(a.titulo.toLowerCase())}</button><button class="btn" data-cancela="${a.id}">Cancelar</button></div>
        <p class="nota">O colega executa no Gateway de pagamentos assim que você confirmar.</p>`;
      else if (ui.abertos[a.id] === "rejeitar") corpo = `<label for="j-${a.id}">Justificativa (obrigatória, vai para o registro)</label><textarea id="j-${a.id}"></textarea>
        <p class="erro" id="e-${a.id}" hidden>Escreva o motivo para o colega e para a auditoria.</p>
        <div class="acoes"><button class="btn btn-pri" data-rejeita="${a.id}">Confirmar recusa</button><button class="btn" data-cancela="${a.id}">Cancelar</button></div>`;
      else corpo = `<div class="acoes"><button class="btn btn-pri" data-aprovar="${a.id}">${ico("i-ok")}Aprovar</button><button class="btn" data-rejeitar="${a.id}">Rejeitar</button><button class="btn btn-link" data-abrir="${a.caso}">Abrir caso</button></div>`;
    } else if (a.estado === "aprovada") corpo = `<p class="nota">Aprovado por ${PESSOA[a.decidido]} às 08:24${a.comentario ? `: "${esc(a.comentario)}"` : ""}.</p>`;
    else corpo = `<p class="nota">Recusado por ${PESSOA[a.decidido]} às 08:24: "${esc(a.justificativa)}".</p>`;
    const sel = a.estado === "pendente" ? "aguardando_aprovacao" : a.estado === "aprovada" ? "resolvida" : "escalada";
    const rot = a.estado === "pendente" ? "Pedido de aprovação" : a.estado === "aprovada" ? "Aprovado" : "Recusado";
    return `<div class="bloco${a.estado !== "pendente" ? " decidido" : ""}" id="bloco-${a.caso}">
      <span class="selo e-${sel}">${rot}</span>
      <div class="bloco-titulo">${esc(a.titulo)} · <span class="mono">${a.caso}</span></div>
      <dl><dt>Motivo</dt><dd>${esc(a.motivo)}</dd>
        <dt>Pedido</dt><dd class="mono">${c.pedido} · ${rs(Number(c.pedidoInfo.valor))}</dd>
        <dt>Alçada</dt><dd>limite ${rs(100)} · já executado no pedido ${rs(0)}</dd>
        <dt>Referência</dt><dd class="mono">${a.id}</dd></dl>
      ${corpo}</div>`;
  }

  function postHTML(p) {
    const novo = ui.novos.has("post-" + (p.id || p.tipo)) ? " novo" : "";
    const av = `<div class="avatar">${ico("i-agente")}</div>`;
    if (p.tipo === "resumo" || p.tipo === "aviso")
      return `<div class="post${novo}">${av}<div class="post-corpo">${autorColega(p.hora)}<div class="post-texto">${p.html}</div></div></div>`;
    if (p.tipo === "aprovacao") {
      const a = aprovacoes[p.id];
      return `<div class="post${novo}">${av}<div class="post-corpo">${autorColega(p.hora)}<div class="post-texto"><span class="mencao">@${PESSOA[a.para]}</span>, preciso da sua aprovação: passa do limite do atendente.</div>${blocoAprovacao(a)}</div></div>`;
    }
    if (p.tipo === "cosmeto") {
      const feito = outrasDecisoes.cosmeto !== "pendente";
      return `<div class="post${novo}">${av}<div class="post-corpo">${autorColega(p.hora)}<div class="post-texto"><span class="mencao">@Paula G.</span>, reação adversa em AT116568. Já orientei a cliente a suspender o uso. Falta o registro de cosmetovigilância.</div>
        <div class="bloco" id="bloco-AT116568"><span class="selo e-${feito ? "resolvida" : "escalada"}">${feito ? "Registrado" : "Escalada"}</span>
          <div class="bloco-titulo">Greens Superfood Maçã Verde · lote <span class="mono">LT2609-D</span></div>
          <dl><dt>Relato</dt><dd>Rosto inchado depois de começar o uso</dd><dt>Pedido</dt><dd class="mono">GBH471000</dd><dt>Cliente quer</dt><dd>Trocar por outro produto (só depois do registro)</dd></dl>
          ${feito ? `<p class="nota">Registrado por ${PESSOA[outrasDecisoes.cosmeto]} às 08:24. A cliente recebe contato da equipe em até 24 h.</p>` :
            `<div class="acoes"><button class="btn btn-pri" data-cosmeto ${ehSupervisor() ? "" : "disabled"}>Registrar cosmetovigilância</button><button class="btn btn-link" data-abrir="AT116568">Abrir caso</button></div>${ehSupervisor() ? "" : `<p class="nota">Só a supervisão registra cosmetovigilância.</p>`}`}
        </div></div></div>`;
    }
    if (p.tipo === "grupo")
      return `<div class="post${novo}">${av}<div class="post-corpo">${autorColega(p.hora)}<div class="post-texto">${p.ids.length} conversas sem regra automática no MVP (dúvidas de produto, pedido não localizado, contato pelo site). Não respondi nada que não pudesse cumprir. Precisam de uma pessoa:</div>
        <div class="bloco"><span class="selo e-escalada">Escalada</span><ul>${p.ids.map((id) => `<li><button class="btn btn-link" data-abrir="${id}">${id}</button></li>`).join("")}</ul></div></div></div>`;
    if (p.tipo === "suspeita") {
      const d = outrasDecisoes.suspeita;
      return `<div class="post${novo}">${av}<div class="post-corpo">${autorColega(p.hora)}<div class="post-texto"><span class="mencao">@Paula G.</span>, replay de 02/10: a foto de AT112299 não fecha com o pedido. Respondi ao cliente de forma neutra e não reenviei.</div>
        <div class="bloco" id="bloco-AT112299"><span class="selo e-${d === "pendente" ? "suspeita" : "resolvida"}">${d === "pendente" ? "Suspeita · decidir em 24 h" : "Decidido"}</span>
          <div class="bloco-titulo">Reenvio de capinha · <span class="mono">GCH544744</span> · ${rs(132.8)}</div>
          <dl><dt>Sinais fortes</dt><dd>imagem repetida de outro pedido; foto anterior à entrega</dd><dt>Aceitar se falsa</dt><dd class="mono">${rs(59.76)}</dd></dl>
          ${d === "pendente" ? (ehSupervisor()
            ? `<div class="acoes"><button class="btn" data-suspeita="aceita">Aceitar reclamação</button><button class="btn btn-pri" data-suspeita="mantida">Manter suspeita</button><button class="btn btn-link" data-abrir="AT112299">Ver evidência</button></div>`
            : `<p class="nota">A decisão da suspeita é da supervisão.</p>`)
            : `<p class="nota">${d === "aceita" ? "Reclamação aceita" : "Suspeita mantida"} por ${PESSOA[outrasDecisoes.suspeitaPor]} às 08:24.</p>`}
        </div></div></div>`;
    }
    if (p.tipo === "resposta")
      return `<div class="post${novo}">${av}<div class="post-corpo">${autorColega(p.hora)}<div class="post-texto">${p.html}</div></div></div>`;
    return "";
  }

  function renderCanal() {
    const el = $("#canal");
    if (!ui.processado) {
      el.innerHTML = `<p class="canal-vazio">Nada por aqui ainda.<br>Quando o colega precisar de alguém, a mensagem chega neste canal, com a evidência junto.</p>`;
      return;
    }
    el.innerHTML = ui.posts.map(postHTML).join("");
    el.querySelector(".post.novo")?.scrollIntoView({ block: "nearest", behavior: reduzir ? "auto" : "smooth" });
    el.querySelectorAll("[data-abrir]").forEach((b) => (b.onclick = () => selecionar(b.dataset.abrir)));
    el.querySelectorAll("[data-aprovar]").forEach((b) => (b.onclick = () => { ui.abertos[b.dataset.aprovar] = "aprovar"; renderCanal(); $(`#c-${b.dataset.aprovar}`)?.focus(); }));
    el.querySelectorAll("[data-rejeitar]").forEach((b) => (b.onclick = () => { ui.abertos[b.dataset.rejeitar] = "rejeitar"; renderCanal(); $(`#j-${b.dataset.rejeitar}`)?.focus(); }));
    el.querySelectorAll("[data-cancela]").forEach((b) => (b.onclick = () => { ui.abertos[b.dataset.cancela] = null; renderCanal(); }));
    el.querySelectorAll("[data-confirma]").forEach((b) => (b.onclick = () => aprovar(b.dataset.confirma, $(`#c-${b.dataset.confirma}`).value.trim())));
    el.querySelectorAll("[data-rejeita]").forEach((b) => (b.onclick = () => {
      const id = b.dataset.rejeita, j = $(`#j-${id}`).value.trim();
      if (!j) { $(`#e-${id}`).hidden = false; $(`#j-${id}`).focus(); return; }
      rejeitar(id, j);
    }));
    const cos = el.querySelector("[data-cosmeto]");
    if (cos) cos.onclick = registrarCosmeto;
    el.querySelectorAll("[data-suspeita]").forEach((b) => (b.onclick = () => decidirSuspeita(b.dataset.suspeita)));
  }

  function irParaCanal(casoId) {
    const b = document.getElementById("bloco-" + casoId);
    if (!b) return;
    b.scrollIntoView({ block: "center", behavior: reduzir ? "auto" : "smooth" });
    b.classList.add("foco");
    setTimeout(() => b.classList.remove("foco"), 1800);
    b.querySelector("button:not([disabled])")?.focus({ preventScroll: true });
  }

  // ---------- Ações de pessoas (só mudam a tela) ----------
  function registrar(linhas) {
    linhas.forEach((l) => ui.extraConsole.push({ hora: "02/11 08:24", aprovado: null, valor: 0, novo: true, ...l }));
  }

  function aprovar(id, comentario) {
    const a = aprovacoes[id], c = porId[a.caso];
    Object.assign(a, { estado: "aprovada", decidido: ui.quem, comentario });
    if (c.aposAprovar) {
      // AT116677: refs reais da jornada E2E (EST000186).
      registrar(c.aposAprovar.map((x) => ({ ...x, conversa: c.id, por: x.por === "supervisor_01" ? ui.quem : x.por, aprovado: x.aprovado ? ui.quem : null })));
    } else {
      registrar([
        { conversa: c.id, sistema: "Canal do time", acao: "aprovar_acao", valor: a.valor, por: ui.quem, aprovado: ui.quem, ref: id },
        { conversa: c.id, sistema: "Gateway de pagamentos", acao: "reembolsar", valor: a.valor, por: "agente", aprovado: ui.quem, ref: "EST-PROTO-01" },
        { conversa: c.id, sistema: "Central de atendimento", acao: "responder_cliente", por: "agente", ref: "MSG-PROTO-02", texto: `Pronto! O reembolso de ${rs(a.valor)} foi feito no seu cartão (protocolo EST-PROTO-01). Pode levar até 2 faturas para aparecer.` },
      ]);
    }
    c.estado = "resolvida";
    const ref = ui.extraConsole.find((x) => x.conversa === c.id && x.acao === "reembolsar")?.ref;
    ui.posts.push({ tipo: "resposta", id: "r-" + id, hora: "08:24", html: `Feito: ${esc(a.titulo.toLowerCase())} em ${c.id} no Gateway de pagamentos (<span class="mono">${esc(ref)}</span>), aprovado por ${PESSOA[ui.quem]}. Avisei a cliente.` });
    ui.novos = new Set([c.id, "post-r-" + id]);
    ui.abertos[id] = null;
    render();
  }

  function rejeitar(id, justificativa) {
    const a = aprovacoes[id], c = porId[a.caso];
    Object.assign(a, { estado: "rejeitada", decidido: ui.quem, justificativa });
    registrar([{ conversa: c.id, sistema: "Canal do time", acao: "rejeitar_acao", valor: a.valor, por: ui.quem, ref: id },
      { conversa: c.id, sistema: "Canal do time", acao: "acionar_pessoa", por: "agente", ref: "MSG-PROTO-03" }]);
    c.estado = "escalada";
    ui.posts.push({ tipo: "resposta", id: "r-" + id, hora: "08:24", html: `Entendido, ${PESSOA[ui.quem]}. Não vou reembolsar ${c.id}. Devolvi o caso para uma pessoa responder a cliente com o motivo.` });
    ui.novos = new Set([c.id, "post-r-" + id]);
    ui.abertos[id] = null;
    render();
  }

  function registrarCosmeto() {
    outrasDecisoes.cosmeto = ui.quem;
    registrar([{ conversa: "AT116568", sistema: "Qualidade", acao: "registrar_cosmetovigilancia", por: ui.quem, ref: "COS-PROTO-01" }]);
    ui.novos = new Set(["AT116568"]);
    render();
  }

  function decidirSuspeita(d) {
    outrasDecisoes.suspeita = d; outrasDecisoes.suspeitaPor = ui.quem;
    const c = porId.AT112299;
    registrar([{ conversa: c.id, sistema: "Canal do time", acao: d === "aceita" ? "decidir_suspeita_aceitar" : "decidir_suspeita_manter", por: ui.quem, ref: "SUS-PROTO-01" }]);
    if (d === "aceita") {
      registrar([{ conversa: c.id, sistema: "OMS", acao: "reenviar_produto", valor: 132.8, por: "agente", ref: "RE-PROTO-01" }]);
      c.estado = "resolvida";
    }
    ui.novos = new Set([c.id]);
    render();
  }

  // ---------- Processar a fila ----------
  async function processar() {
    ui.processado = true;
    montarPosts();
    const ids = filaDe().map((c) => c.id);
    ui.novos = new Set(reduzir ? [] : ids);
    render();
    setTimeout(() => { ui.novos = new Set(); }, 400);
  }

  function selecionar(id) {
    ui.selecionado = id; ui.marcarRef = null;
    render();
    $("#caso").scrollTop = 0;
    document.querySelector(`.item[data-id="${id}"]`)?.scrollIntoView({ block: "nearest" });
  }

  function render() {
    renderPlacar(); renderCanais(); renderFila(); renderCaso(); renderConsole(); renderCanal();
  }

  // ---------- Ligações fixas ----------
  $("#busca").addEventListener("input", (e) => { ui.busca = e.target.value; renderFila(); });
  document.querySelectorAll("[data-escopo]").forEach((b) => (b.onclick = () => { ui.escopo = b.dataset.escopo; renderConsole(); }));
  $("#identidade").addEventListener("change", (e) => { ui.quem = e.target.value; renderCanal(); });
  addEventListener("resize", () => document.documentElement.style.setProperty("--placar-h", $("#placar").offsetHeight + "px"));
  const qs = new URLSearchParams(location.search);
  if (qs.get("caso") && porId[qs.get("caso")]) ui.selecionado = qs.get("caso");
  if (qs.has("processado")) { ui.processado = true; montarPosts(); }
  render();
})();
