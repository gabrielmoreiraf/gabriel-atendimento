// Cliente HTTP da API do agente. Sem regra de negócio: só busca e dispara.
import { agrupar } from "./agrupar";
import type {
  Caso,
  EventoApi,
  ItemFila,
  ItemReplay,
  MensagemCanal,
  PadraoAnalista,
  Placar,
  RegistroAcao,
  RespostaVigia,
  ResultadoTratamento,
  SuspeitaPendente,
} from "./tipos";

export class ErroApi extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ErroApi";
  }
}

async function pedir<T>(caminho: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`/api${caminho}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!resp.ok) {
    let detalhe = `${resp.status} ${resp.statusText}`;
    try {
      const corpo = await resp.json();
      if (typeof corpo?.detail === "string") detalhe = corpo.detail;
      else if (corpo?.detail) detalhe = JSON.stringify(corpo.detail);
    } catch {
      // corpo sem JSON: fica o status
    }
    throw new ErroApi(resp.status, detalhe);
  }
  return (await resp.json()) as T;
}

const post = <T>(caminho: string, corpo?: unknown) =>
  pedir<T>(caminho, {
    method: "POST",
    body: corpo === undefined ? undefined : JSON.stringify(corpo),
  });

/** Demo do WhatsApp: cliente da base (nome mascarado) e os pedidos dele. */
export interface ClienteSimulado {
  customer_id: string;
  nome: string;
  pedidos: {
    order_id: string;
    marca: string;
    status_entrega: string | null;
    valor: number | null;
    descricao_produto: string | null;
  }[];
}

export interface RespostaSimulada {
  /** null quando a mensagem é só cumprimento ou agradecimento (não abre caso). */
  conversation_id: string | null;
  resposta: string;
  estado: string;
  mensagens: { autor: string; texto: string }[];
}

/** O que está ligado no deploy (GET /api/saude); sem segredos. */
export interface Saude {
  leitor: string;
  slack: { modo: string | null; falhas: number } | null;
}

export interface Api {
  /** Opcional: o modo de exemplo não tem backend para dizer o que está ligado. */
  saude?(): Promise<Saude>;
  /** Opcionais: só o backend real tem o simulador de WhatsApp. */
  simuladorClientes?(): Promise<ClienteSimulado[]>;
  simuladorMensagem?(corpo: {
    customer_id: string;
    order_id?: string;
    texto: string;
    anterior?: string;
  }): Promise<RespostaSimulada>;
  fila(): Promise<ItemFila[]>;
  processarFila(): Promise<Placar>;
  processarConversa(id: string): Promise<Caso>;
  caso(id: string): Promise<Caso>;
  acoes(): Promise<RegistroAcao[]>;
  canal(): Promise<MensagemCanal[]>;
  placar(): Promise<Placar>;
  aprovar(aprovacaoId: string, supervisorId: string, comentario?: string): Promise<unknown>;
  rejeitar(aprovacaoId: string, supervisorId: string, justificativa: string): Promise<unknown>;
  casosReplay(): Promise<ItemReplay[]>;
  processarReplay(id: string): Promise<Caso>;
  padroes(): Promise<PadraoAnalista[]>;
  tratarPadrao(tipo: string): Promise<ResultadoTratamento>;
  alertasVigia(agoraIso: string): Promise<RespostaVigia>;
  rodarVigia(agoraIso: string): Promise<unknown>;
  suspeitas(): Promise<SuspeitaPendente[]>;
  reiniciarDemo(): Promise<unknown>;
  decidirSuspeita(
    suspeitaId: string,
    supervisorId: string,
    decisao: "procedente" | "improcedente",
    justificativa: string,
  ): Promise<Caso>;
}

export const apiHttp: Api = {
  saude: () => pedir("/saude"),
  simuladorClientes: () => pedir("/simulador/clientes"),
  simuladorMensagem: (corpo) => post("/simulador/mensagem", corpo),
  fila: () => pedir("/fila"),
  processarFila: () => post("/fila/processar"),
  processarConversa: (id) => post(`/conversas/${encodeURIComponent(id)}/processar`),
  caso: (id) => pedir(`/conversas/${encodeURIComponent(id)}`),
  acoes: () => pedir("/acoes"),
  canal: () => pedir("/canal"),
  placar: () => pedir("/placar"),
  aprovar: (id, supervisor_id, comentario) =>
    post(`/aprovacoes/${encodeURIComponent(id)}/aprovar`, { supervisor_id, comentario }),
  rejeitar: (id, supervisor_id, justificativa) =>
    post(`/aprovacoes/${encodeURIComponent(id)}/rejeitar`, { supervisor_id, justificativa }),
  casosReplay: () => pedir("/replay/casos"),
  processarReplay: (id) => post(`/replay/${encodeURIComponent(id)}/processar`),
  padroes: () => pedir("/analista/padroes"),
  tratarPadrao: (tipo) => post(`/analista/padroes/${encodeURIComponent(tipo)}/tratar`),
  alertasVigia: (agoraIso) => pedir(`/vigia/alertas?agora=${encodeURIComponent(agoraIso)}`),
  suspeitas: () => pedir("/suspeitas"),
  reiniciarDemo: () => post("/demo/reiniciar"),
  decidirSuspeita: (id, supervisor_id, decisao, justificativa) =>
    post(`/suspeitas/${encodeURIComponent(id)}/decidir`, { supervisor_id, decisao, justificativa }),
  rodarVigia: (agoraIso) => post(`/vigia/rodar?agora=${encodeURIComponent(agoraIso)}`),
};

function lerEvento(dados: unknown): EventoApi | null {
  if (typeof dados !== "string") return null;
  try {
    const ev = JSON.parse(dados);
    return ev && typeof ev.tipo === "string" ? (ev as EventoApi) : null;
  } catch {
    return null;
  }
}

export interface OpcoesEventos {
  /** Intervalo do polling de reserva enquanto o stream está fora (ms). */
  pollingMs?: number;
  /** Espera máxima entre tentativas de reconexão (ms). */
  reconexaoMaxMs?: number;
}

/**
 * Assina o SSE `/api/eventos`. Eventos de `leitura` (progresso do leitor) chegam na hora,
 * com o próprio evento; os demais viram uma recarga agrupada, sem argumento.
 *
 * No Vercel a função do stream termina no tempo máximo: quando o stream cai, reconecta com
 * `?desde=<último id>` (com espera crescente) e, enquanto estiver fora, recarrega por polling.
 * Ids já vistos são descartados, então `desde` inclusivo ou exclusivo funciona igual.
 * Devolve a função que fecha tudo.
 */
export function assinarEventos(
  aoEvento: (evento?: EventoApi) => void,
  { pollingMs = 5000, reconexaoMaxMs = 30_000 }: OpcoesEventos = {},
): () => void {
  if (typeof EventSource === "undefined") return () => {};
  // ao conectar, o backend pode reenviar o histórico: agrupa a rajada numa recarga só
  const recarregar = agrupar(() => aoEvento(), 250);
  let fonte: EventSource | null = null;
  let ultimoId: number | null = null;
  let falhas = 0;
  let encerrado = false;
  let polling: ReturnType<typeof setInterval> | undefined;
  let reconexao: ReturnType<typeof setTimeout> | undefined;

  const pararPolling = () => {
    clearInterval(polling);
    polling = undefined;
  };

  function conectar() {
    if (encerrado) return;
    const url = ultimoId === null ? "/api/eventos" : `/api/eventos?desde=${ultimoId}`;
    const atual = new EventSource(url);
    fonte = atual;
    atual.onopen = () => {
      falhas = 0;
      pararPolling();
    };
    atual.onmessage = (msg: MessageEvent) => {
      const id = Number.parseInt(msg.lastEventId, 10);
      if (Number.isFinite(id)) {
        if (ultimoId !== null && id <= ultimoId) return; // já visto antes da reconexão
        ultimoId = id;
      }
      const ev = lerEvento(msg.data);
      if (ev?.tipo === "leitura") aoEvento(ev);
      else recarregar();
    };
    // eventos nomeados (event: acao / aprovacao / canal) também disparam recarga
    for (const nome of ["acao", "aprovacao", "canal", "placar", "conversa", "incidente", "vigia"]) {
      atual.addEventListener(nome, () => recarregar());
    }
    atual.onerror = () => {
      // controla a reconexão aqui (com `desde`), em vez da automática do navegador
      atual.close();
      if (encerrado) return;
      if (polling === undefined) {
        aoEvento();
        polling = setInterval(() => aoEvento(), pollingMs);
      }
      const espera = Math.min(1000 * 2 ** falhas, reconexaoMaxMs);
      falhas += 1;
      clearTimeout(reconexao);
      reconexao = setTimeout(conectar, espera);
    };
  }

  conectar();
  return () => {
    encerrado = true;
    fonte?.close();
    pararPolling();
    clearTimeout(reconexao);
  };
}
