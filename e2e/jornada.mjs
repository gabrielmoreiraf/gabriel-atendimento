// Jornada E2E do MVP (camada 5, playwright-skill).
// Abre a demo, processa a fila, confere reação adversa (AT116568) e um caso de suspeita,
// testa a autoaprovação (HG-03) e aprova um pedido no canal do time (HP-10).
// Evidências: .scratch/e2e/ (screenshots, vídeo .webm e .mp4, relatorio.json).
// Como rodar: ver e2e/README.md.

import { execFileSync } from "node:child_process";
import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const BASE_URL = process.env.E2E_URL || "http://localhost:5173";
const SAIDA = path.resolve(process.env.E2E_SAIDA || path.join(RAIZ, ".scratch", "e2e"));
const HEADLESS = process.env.PW_HEADLESS !== "false";
const TIMEOUT_PROCESSAR_MS = Number(process.env.E2E_TIMEOUT_PROCESSAR_MS || 180_000);
const CONVERSA_REACAO = "AT116568"; // M10: única reação adversa na fila
const SUPERVISORES = ["supervisor_01", "supervisor_02", "supervisor_03"]; // web/src/equipe.ts

// Playwright vem da skill (run.js define PW_SKILL_DIR); fora dela, do node_modules local.
const requerer = createRequire(
  process.env.PW_SKILL_DIR ? path.join(process.env.PW_SKILL_DIR, "package.json") : import.meta.url,
);
const { chromium } = requerer("playwright");

const resultados = [];
function conferir(nome, ok, detalhe = "") {
  resultados.push({ nome, ok: Boolean(ok), detalhe });
  console.log(`${ok ? "OK  " : "FALHA"} ${nome}${detalhe ? ` — ${detalhe}` : ""}`);
}
// Elemento que a interface ainda não tem: registra, sem contar como falha.
const indisponiveis = [];
function naoDisponivel(nome, detalhe = "") {
  indisponiveis.push({ nome, detalhe });
  console.log(`N/D   ${nome}${detalhe ? ` — ${detalhe}` : ""}`);
}
// Texto ao cliente nunca acusa (HG-07).
const PALAVRAS_PROIBIDAS = ["fraude", "golpe", "mentira", "falso", "falsa", "suspeita"];
const proibidaEm = (texto) => PALAVRAS_PROIBIDAS.find((p) => texto.toLowerCase().includes(p));
const SINAIS_FORTES = ["hash_repetido", "captura_antes_da_entrega", "editor_de_imagem"];
const CONVERSA_REPLAY = process.env.E2E_REPLAY || "AT104936"; // EC-16/EC-17 na base
const PADRAO_ANALISTA = process.env.E2E_PADRAO || "cobranca_em_dobro";
const api = (caminho) => new URL(caminho, BASE_URL).href;
const VIGIA_AGORA = process.env.E2E_VIGIA_AGORA || "2026-11-02T08:20:00";
const VIGIA_LEMBRETE = process.env.E2E_VIGIA_LEMBRETE || "2026-11-02T10:00:00";

let passo = 0;
async function foto(page, nome) {
  passo += 1;
  const arquivo = path.join(SAIDA, `${String(passo).padStart(2, "0")}-${nome}.png`);
  await page.screenshot({ path: arquivo, fullPage: true });
  return arquivo;
}

async function lerPlacar(page) {
  const placar = page.getByTestId("placar");
  await placar.waitFor();
  const rotulos = await placar.locator("dt").allInnerTexts();
  const valores = await placar.locator("dd").allInnerTexts();
  return Object.fromEntries(rotulos.map((r, i) => [r.trim(), valores[i]?.trim()]));
}

async function abrirCaso(page, conversationId) {
  await page.getByTestId("fila-item").filter({ hasText: conversationId }).first().click();
  const titulo = page.locator("#caso-titulo");
  await titulo.filter({ hasText: conversationId }).waitFor({ timeout: 15_000 });
  return page.locator("section.caso");
}

function idsNoTexto(texto) {
  return [...new Set(texto.match(/\b(?:atendente|analista|supervisor)_\d+\b/g) ?? [])];
}

async function principal() {
  fs.mkdirSync(SAIDA, { recursive: true });
  const dirVideo = path.join(SAIDA, "video");
  fs.rmSync(dirVideo, { recursive: true, force: true });

  const browser = await chromium.launch({ headless: HEADLESS, slowMo: Number(process.env.SLOW_MO || 0) });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    recordVideo: { dir: dirVideo, size: { width: 1440, height: 900 } },
  });
  const page = await context.newPage();
  const errosConsole = [];
  page.on("console", (m) => m.type() === "error" && errosConsole.push(m.text()));
  page.on("pageerror", (e) => errosConsole.push(String(e)));

  try {
    // 1. Abre a página e captura o placar inicial
    await page.goto(BASE_URL);
    const placarAntes = await lerPlacar(page);
    await page.getByTestId("fila-item").first().waitFor({ timeout: 15_000 }).catch(() => {});
    const filaAntes = await page.getByTestId("fila-item").count();
    conferir("fila carregada", filaAntes > 0, `${filaAntes} conversas`);
    const titulo = (await page.locator("h1").first().innerText().catch(() => "")).trim();
    conferir("nome Gabriel no cabeçalho", /\bFIO\b/.test(titulo), titulo);
    await foto(page, "inicio");

    // 1b. Vigia às 08:20 (HG-20): avisa o canal do SLA sem ser perguntado, sem repetir aviso
    const msgsAntes = await page.getByTestId("canal-msg").count();
    const botaoVigia = page.getByTestId("btn-vigia-0820");
    let postados = null;
    if ((await botaoVigia.count()) > 0) {
      await botaoVigia.first().click();
    } else {
      naoDisponivel("botão do vigia (btn-vigia-0820)", "acionado pela API");
      const resp = await page.request.post(api(`/api/vigia/rodar?agora=${VIGIA_AGORA}`));
      const corpo = resp.ok() ? await resp.json().catch(() => ({})) : {};
      postados = corpo.postados?.length ?? 0;
      conferir("vigia rodou (API)", resp.ok(), `HTTP ${resp.status()} postados=${postados}`);
    }
    const chegaram = await page
      .waitForFunction(
        (antes) => document.querySelectorAll('[data-testid="canal-msg"]').length > antes,
        msgsAntes,
        { timeout: 10_000 },
      )
      .then(() => true)
      .catch(() => false);
    const msgsDepois = await page.getByTestId("canal-msg").count();
    conferir("vigia postou avisos no canal", chegaram, `canal ${msgsAntes} → ${msgsDepois}`);
    const repetida = await page.request.post(api(`/api/vigia/rodar?agora=${VIGIA_AGORA}`));
    const segunda = repetida.ok() ? await repetida.json().catch(() => ({})) : {};
    conferir(
      "vigia não repete aviso já postado",
      repetida.ok() && (segunda.postados?.length ?? -1) === 0,
      `2ª rodada: postados=${segunda.postados?.length} ja_postados=${segunda.ja_postados}`,
    );
    await page.getByTestId("canal-msg").last().scrollIntoViewIfNeeded().catch(() => {});
    await foto(page, "vigia-canal");


    // 2. Processa a fila e espera ações no console
    await page.getByTestId("btn-processar").click();
    await page.getByTestId("console-acao").first().waitFor({ timeout: TIMEOUT_PROCESSAR_MS });
    await page.getByTestId("btn-processar").filter({ hasText: "Processar fila" }).waitFor({
      timeout: TIMEOUT_PROCESSAR_MS,
    });
    const placarDepois = await lerPlacar(page);
    const nAcoes = await page.getByTestId("console-acao").count();
    conferir("ações no console após processar", nAcoes > 0, `${nAcoes} ações`);
    conferir(
      "placar mudou após processar",
      JSON.stringify(placarAntes) !== JSON.stringify(placarDepois),
      JSON.stringify(placarDepois),
    );
    // 2b. Placar da tela = GET /api/placar (sem números fixos no script)
    const placarApi = await page.request
      .get(api("/api/placar"))
      .then((r) => (r.ok() ? r.json() : {}))
      .catch(() => ({}));
    const campos = {
      "Resolvidas sozinho": "resolvidas_sozinho",
      "Aguardando aprovação": "aguardando_aprovacao",
      "Aguardando cliente": "aguardando_cliente",
      Suspeitas: "suspeitas",
      Escaladas: "escaladas",
    };
    const divergentes = Object.entries(campos)
      .filter(([rotulo, chave]) => String(placarApi[chave]) !== placarDepois[rotulo])
      .map(([rotulo, chave]) => `${rotulo}: tela=${placarDepois[rotulo]} api=${placarApi[chave]}`);
    conferir(
      "placar da tela confere com GET /api/placar",
      divergentes.length === 0 && Object.keys(placarApi).length > 0,
      divergentes.join("; ") ||
        Object.values(campos)
          .map((c) => `${c}=${placarApi[c]}`)
          .join(" "),
    );
    await foto(page, "fila-processada");

    // 3. Caso de reação adversa: escalado, sem resolução sozinho
    const itemReacao = page.getByTestId("fila-item").filter({ hasText: CONVERSA_REACAO }).first();
    if ((await itemReacao.count()) === 0) {
      conferir(`${CONVERSA_REACAO} presente na fila`, false, "conversa não encontrada");
    } else {
      const estadoReacao = await itemReacao.getAttribute("data-estado");
      conferir(
        `${CONVERSA_REACAO} escalada (reação adversa)`,
        estadoReacao === "escalada",
        `estado=${estadoReacao}`,
      );
      const casoReacao = await abrirCaso(page, CONVERSA_REACAO);
      const textoReacao = await casoReacao.innerText();
      conferir(
        `${CONVERSA_REACAO} mostra decisão da política`,
        !textoReacao.includes("Ainda não processada"),
        textoReacao.match(/Decisão da política\s*\n([^\n]+)/)?.[1] ?? "",
      );
      await foto(page, "caso-reacao-adversa");
    }

    // 4. Um caso de suspeita: sinais de evidência e resposta neutra (HG-07)
    const itemSuspeita = page.locator('[data-testid="fila-item"][data-estado="suspeita"]').first();
    const temSuspeita = (await itemSuspeita.count()) > 0;
    if (temSuspeita || placarDepois.Suspeitas !== "0") {
      conferir("existe caso em suspeita", temSuspeita, `placar Suspeitas=${placarDepois.Suspeitas}`);
    } else {
      // fila_aberta.csv (02/11 08h) não tem anexos: nenhum sinal forte possível (EC-16/17)
      conferir("suspeita: não se aplica nesta fila", true, "placar Suspeitas=0 e nenhum item em suspeita");
    }
    if (temSuspeita) {
      const idSuspeita = (await itemSuspeita.locator(".mono").first().innerText()).trim();
      const casoSuspeita = await abrirCaso(page, idSuspeita);
      const sinais = await casoSuspeita.locator("ul.sinais li").count();
      conferir(`${idSuspeita} lista sinais verificáveis`, sinais > 0, `${sinais} sinais`);
      const resposta = (await casoSuspeita.locator("blockquote.resposta").allInnerTexts()).join(" ");
      const proibida = ["fraude", "golpe", "mentira", "falso", "falsa", "suspeita"].find((p) =>
        resposta.toLowerCase().includes(p),
      );
      conferir(`${idSuspeita} resposta ao cliente sem acusação`, !proibida, proibida ?? "neutra");
      await foto(page, "caso-suspeita");
    }

    // 5. Pedido de aprovação no canal do time
    const primeiraPendente = page
      .locator('[data-testid="canal-msg"][data-tipo="aprovacao"]')
      .filter({ has: page.getByTestId("btn-aprovar") })
      .first();
    const temAprovacao = (await primeiraPendente.count()) > 0;
    conferir("existe pedido de aprovação pendente no canal", temAprovacao);
    if (temAprovacao) {
      const ref = (await primeiraPendente.locator(".canal__ref").allInnerTexts())[0] ?? "";
      const conv = ref.match(/AT\d{6}/)?.[0] ?? "";
      // fixa a mensagem desta conversa (o .first() acima mudaria depois da aprovação)
      const msgAprovacao = page
        .locator('[data-testid="canal-msg"][data-tipo="aprovacao"]')
        .filter({ hasText: conv })
        .filter({ has: page.getByTestId("btn-aprovar") })
        .first();
      await msgAprovacao.scrollIntoViewIfNeeded();
      const textoMsg = await msgAprovacao.locator(".canal__texto").innerText();
      // dados brutos da mensagem (aprovacao_id, solicitante); no modo mock do front não há API
      const canalApi = await page.request
        .get(new URL("/api/canal", BASE_URL).href)
        .then((r) => (r.ok() ? r.json() : []))
        .catch(() => []);
      const bruto = Array.isArray(canalApi)
        ? canalApi.find((m) => m.tipo === "aprovacao" && m.conversation_id === conv && m.aprovacao_id)
        : undefined;
      const aprovacaoId = bruto?.aprovacao_id;
      const solicitante =
        process.env.E2E_SOLICITANTE ??
        bruto?.solicitado_por ??
        bruto?.executado_por ??
        idsNoTexto(textoMsg).find((id) => id !== bruto?.para);
      await foto(page, "canal-pedido-aprovacao");

      // 5a. Autoaprovação (HG-03): quem pediu tenta aprovar e a API recusa
      const select = msgAprovacao.locator("select");
      if (solicitante && SUPERVISORES.includes(solicitante)) {
        await select.selectOption(solicitante);
        await msgAprovacao.getByTestId("btn-aprovar").click();
        const alerta = msgAprovacao.getByRole("alert");
        await alerta.waitFor({ timeout: 10_000 }).catch(() => {});
        const textoAlerta = (await alerta.count()) ? await alerta.innerText() : "";
        conferir("autoaprovação recusada na tela", textoAlerta.includes("Recusado"), textoAlerta);
        await foto(page, "autoaprovacao-recusada");
      } else {
        // solicitante não é supervisor (ex.: o agente): a tela não oferece a opção, testa direto na API
        const quem = solicitante ?? "agente";
        const resp = await page.request.post(
          new URL(`/api/aprovacoes/${encodeURIComponent(aprovacaoId ?? "")}/aprovar`, BASE_URL).href,
          { data: { supervisor_id: quem } },
        );
        const motivo = await resp
          .json()
          .then((c) => c?.detail ?? "")
          .catch(() => "");
        conferir(
          "autoaprovação recusada pela API",
          resp.status() === 403,
          `solicitante=${quem}, HTTP ${resp.status()}: ${motivo}`,
        );
      }

      // 5b. Aprova com um supervisor diferente do solicitante
      const sugerido = SUPERVISORES.includes(bruto?.para) ? bruto.para : SUPERVISORES[0];
      const aprovador =
        sugerido !== solicitante ? sugerido : SUPERVISORES.find((s) => s !== solicitante);
      await select.selectOption(aprovador);
      await msgAprovacao.locator("input[type=text]").fill("Aprovado na jornada E2E");
      await foto(page, "aprovando");
      await msgAprovacao.getByTestId("btn-aprovar").click();
      const decidida = page
        .locator('[data-testid="canal-msg"][data-tipo="aprovacao"]')
        .filter({ hasText: conv })
        .locator('.canal__decidida[data-estado="aprovada"]');
      const aprovada = await decidida
        .first()
        .waitFor({ timeout: 15_000 })
        .then(() => true)
        .catch(() => false);
      conferir("pedido marcado como aprovado no canal", aprovada, `${conv} por ${aprovador}`);

      // 6. Ação aprovada aparece no console com o aprovador
      const linha = page
        .getByTestId("console-acao")
        .filter({ hasText: conv })
        .filter({ hasText: aprovador })
        .first();
      const apareceu = await linha
        .waitFor({ timeout: 15_000 })
        .then(() => true)
        .catch(() => false);
      conferir(
        "ação aprovada no console",
        apareceu,
        `${conv} aprovacao=${aprovacaoId} aprovador=${aprovador} solicitante=${solicitante ?? "?"}`,
      );
      if (apareceu) await linha.scrollIntoViewIfNeeded();
      await foto(page, "acao-aprovada-console");
    }

    // 7. Pedidos de foto ficam aguardando o cliente (não contam como resolvidos)
    const aguardando = await page.locator('[data-testid="fila-item"][data-estado="aguardando_cliente"]').count();
    const filaApi = await page.request
      .get(api("/api/fila"))
      .then((r) => (r.ok() ? r.json() : []))
      .catch(() => []);
    const aguardandoApi = filaApi.filter((c) => c.estado === "aguardando_cliente").length;
    conferir(
      "pedidos de foto em aguardando_cliente",
      aguardando > 0 && aguardando === aguardandoApi,
      `tela=${aguardando} api=${aguardandoApi}`,
    );
    if (aguardando > 0) {
      const id = (await page
        .locator('[data-testid="fila-item"][data-estado="aguardando_cliente"] .mono')
        .first()
        .innerText()).trim();
      const caso = await abrirCaso(page, id);
      const resposta = (await caso.locator("blockquote.resposta").allInnerTexts()).join(" ");
      conferir(`${id} pede foto ao cliente`, /foto/i.test(resposta), resposta.slice(0, 80));
      await foto(page, "aguardando-cliente");
    }

    // 8. Verificação de evidência por replay (F3): caso real com sinal forte
    const itemReplay = page.getByTestId("replay-item").filter({ hasText: CONVERSA_REPLAY }).first();
    if ((await page.getByTestId("replay-item").count()) === 0) {
      naoDisponivel("seção de replay na tela", "sem replay-item; conferindo pela API");
      const resp = await page.request.post(api(`/api/replay/${CONVERSA_REPLAY}/processar`));
      const caso = resp.ok() ? await resp.json() : null;
      const tipos = (caso?.veredicto?.sinais ?? []).map((s) => s.tipo);
      conferir(
        `${CONVERSA_REPLAY} replay (API) com sinal forte`,
        tipos.some((t) => SINAIS_FORTES.includes(t)),
        `HTTP ${resp.status()} sinais=${tipos.join(",")}`,
      );
      const proibida = proibidaEm(caso?.resposta_ao_cliente ?? "");
      conferir(`${CONVERSA_REPLAY} replay: resposta neutra`, caso && !proibida, proibida ?? "neutra");
    } else if ((await itemReplay.count()) === 0) {
      conferir(`${CONVERSA_REPLAY} na lista de replay`, false, "conversa não listada");
    } else {
      await itemReplay.scrollIntoViewIfNeeded();
      await itemReplay.getByTestId("btn-replay").click();
      const sinais = page.getByTestId("sinal-evidencia");
      await sinais.first().waitFor({ timeout: 30_000 }).catch(() => {});
      const tipos = await sinais.evaluateAll((els) => els.map((e) => e.getAttribute("data-tipo")));
      conferir(
        `${CONVERSA_REPLAY} replay com sinal forte`,
        tipos.some((t) => SINAIS_FORTES.includes(t)),
        `sinais=${tipos.join(",")}`,
      );
      const resultado = page.locator(".verificacao__resultado");
      const resposta = (await resultado.locator("blockquote.resposta").allInnerTexts()).join(" ");
      const proibida = proibidaEm(resposta);
      conferir(
        `${CONVERSA_REPLAY} replay: resposta ao cliente neutra`,
        resposta.length > 0 && !proibida,
        proibida ?? resposta.slice(0, 90),
      );
      await resultado.scrollIntoViewIfNeeded();
      await foto(page, "replay-evidencia");

      // 8b. Supervisor decide a suspeita na tela (HG-04/HG-07): improcedente, outro supervisor
      const suspeitas = await page.request
        .get(api("/api/suspeitas"))
        .then((r) => (r.ok() ? r.json() : []))
        .catch(() => []);
      const suspeita = suspeitas.find((x) => x.conversation_id === CONVERSA_REPLAY);
      const painel = page.locator(".verificacao__suspeita").first();
      if (!suspeita) {
        conferir(`${CONVERSA_REPLAY} tem suspeita pendente`, false, "GET /api/suspeitas sem a conversa");
      } else {
        // quem sinalizou não decide: a tela não oferece essa pessoa, então a recusa vai pela API
        const recusa = await page.request.post(
          api(`/api/suspeitas/${encodeURIComponent(suspeita.suspeita_id)}/decidir`),
          {
            data: {
              supervisor_id: suspeita.sinalizado_por,
              decisao: "improcedente",
              justificativa: "teste E2E: quem sinalizou tenta decidir",
            },
          },
        );
        const motivoRecusa = await recusa
          .json()
          .then((c) => c?.detail ?? "")
          .catch(() => "");
        conferir(
          "quem sinalizou não decide a suspeita (API)",
          recusa.status() === 403,
          `sinalizado_por=${suspeita.sinalizado_por}, HTTP ${recusa.status()}: ${motivoRecusa}`,
        );
        if ((await painel.getByTestId("btn-suspeita-improcedente").count()) === 0) {
          naoDisponivel("decisão da suspeita na tela", "sem btn-suspeita-improcedente");
        } else {
          const select = painel.locator("select");
          const opcoes = await select.locator("option").evaluateAll((os) => os.map((o) => o.value));
          const decisor = opcoes.find((o) => o && o !== suspeita.sinalizado_por);
          await select.selectOption(decisor);
          await painel
            .locator("input[type=text], textarea")
            .first()
            .fill("Hash e data de captura conferidos com o cliente; evidência explicada.");
          await painel.scrollIntoViewIfNeeded();
          await foto(page, "suspeita-decidindo");
          await painel.getByTestId("btn-suspeita-improcedente").click();
          const decidida = page.locator('.suspeita__decidida[data-estado="improcedente"]').first();
          const ok = await decidida
            .waitFor({ timeout: 15_000 })
            .then(() => true)
            .catch(() => false);
          conferir("suspeita decidida improcedente na tela", ok, `por ${decisor}`);
          const caso = await page.request
            .get(api(`/api/conversas/${CONVERSA_REPLAY}`))
            .then((r) => (r.ok() ? r.json() : {}))
            .catch(() => ({}));
          const acoes = (caso.acoes ?? []).map((a) => a.acao);
          conferir(
            `${CONVERSA_REPLAY} encerrada após a decisão`,
            caso.conversa?.estado === "resolvida" && acoes.includes("encerrar_conversa"),
            `estado=${caso.conversa?.estado} encerrar_conversa=${acoes.includes("encerrar_conversa")}`,
          );
          const resposta = caso.resposta_ao_cliente ?? "";
          const proibida = proibidaEm(resposta);
          conferir(
            `${CONVERSA_REPLAY} resposta final ao cliente neutra`,
            resposta.length > 0 && !proibida,
            proibida ?? resposta.slice(0, 90),
          );
          await foto(page, "suspeita-decidida");
        }
      }
    }

    // 9. Agente analista: padrão de cobrança em dobro vira incidente INC- no console
    const itemPadrao = page.locator(`[data-testid="padrao-item"][data-tipo="${PADRAO_ANALISTA}"]`);
    const botaoAnalista = itemPadrao.getByTestId("btn-tratar-padrao");
    let incidente = null;
    if ((await botaoAnalista.count()) > 0) {
      await itemPadrao.scrollIntoViewIfNeeded();
      await botaoAnalista.first().click();
      const resultado = itemPadrao.getByTestId("resultado-padrao");
      await resultado.waitFor({ timeout: 15_000 }).catch(() => {});
      const texto = (await resultado.count()) ? await resultado.innerText() : "";
      incidente = texto.match(/INC-\d+/)?.[0] ?? null;
      conferir("analista tratou o padrão na tela", Boolean(texto), texto.replace(/\s+/g, " ").slice(0, 90));
      await foto(page, "analista-resultado");
    } else {
      naoDisponivel("botão do agente analista", "acionado pela API");
      const resp = await page.request.post(api(`/api/analista/padroes/${PADRAO_ANALISTA}/tratar`));
      const corpo = resp.ok() ? await resp.json().catch(() => ({})) : {};
      incidente = JSON.stringify(corpo).match(/INC-\d+/)?.[0] ?? null;
      conferir("analista tratou o padrão (API)", resp.ok(), `HTTP ${resp.status()} ${incidente ?? ""}`);
    }
    const linhaInc = page
      .getByTestId("console-acao")
      .filter({ hasText: incidente ?? /INC-\d+/ })
      .first();
    let noConsole = await linhaInc
      .waitFor({ timeout: 10_000 })
      .then(() => true)
      .catch(() => false);
    if (!noConsole) {
      await page.reload(); // sem SSE na hora: recarrega e confere de novo
      noConsole = await linhaInc
        .waitFor({ timeout: 10_000 })
        .then(() => true)
        .catch(() => false);
    }
    const textoInc = noConsole ? await linhaInc.innerText() : "";
    conferir("incidente INC- no console", noConsole, textoInc.match(/INC-\d+/)?.[0] ?? incidente ?? "");
    if (noConsole) await linhaInc.scrollIntoViewIfNeeded();
    await foto(page, "analista-incidente");

    // 10. Vigia às 10:00: lembra o supervisor da aprovação que ficou pendente (HG-21)
    const lembrete = await page.request.post(api(`/api/vigia/rodar?agora=${VIGIA_LEMBRETE}`));
    const corpoLembrete = lembrete.ok() ? await lembrete.json().catch(() => ({})) : {};
    const lembretes = (corpoLembrete.postados ?? []).filter((a) => a.aprovacao_id);
    conferir(
      "vigia lembra aprovação pendente às 10:00",
      lembrete.ok() && lembretes.length > 0,
      `HTTP ${lembrete.status()} lembretes=${lembretes.map((a) => a.aprovacao_id).join(",")}`,
    );

    conferir("sem erro de JavaScript na página", errosConsole.length === 0, errosConsole.slice(0, 3).join(" | "));
    await page.waitForTimeout(1_000); // último quadro do vídeo
  } catch (erro) {
    conferir("jornada concluída sem exceção", false, String(erro?.message ?? erro).split("\n")[0]);
    await foto(page, "erro").catch(() => {});
  } finally {
    const video = page.video();
    await context.close();
    await browser.close();
    if (video) {
      const webm = await video.path();
      const destino = path.join(SAIDA, "jornada.webm");
      fs.copyFileSync(webm, destino);
      try {
        execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", destino, "-c:v", "libx264", "-pix_fmt", "yuv420p", path.join(SAIDA, "jornada.mp4")]);
        console.log(`vídeo: ${path.join(SAIDA, "jornada.mp4")}`);
      } catch {
        console.log(`ffmpeg indisponível; vídeo em ${destino}`);
      }
    }
  }

  const falhas = resultados.filter((r) => !r.ok);
  fs.writeFileSync(
    path.join(SAIDA, "relatorio.json"),
    JSON.stringify({ url: BASE_URL, resultados, falhas: falhas.length, indisponiveis }, null, 2),
  );
  console.log(
    `\n${resultados.length - falhas.length}/${resultados.length} verificações OK` +
      (indisponiveis.length ? `, ${indisponiveis.length} não disponíveis` : "") +
      `. Evidências em ${SAIDA}`,
  );
  process.exitCode = falhas.length ? 1 : 0;
}

await principal();
