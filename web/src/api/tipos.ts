// Tipos do contrato da API (SPEC.md, seção "API"). Espelham as respostas do backend.

export type EstadoConversa =
  | "aberta"
  | "resolvida"
  | "aguardando_aprovacao"
  | "aguardando_cliente"
  | "suspeita"
  | "escalada";

export interface ItemFila {
  conversation_id: string;
  canal: string;
  marca: string;
  assunto: string;
  order_id: string | null;
  data_abertura: string;
  prioridade: string | number | null;
  estado: EstadoConversa;
}

export interface Mensagem {
  autor: string;
  timestamp: string;
  texto: string;
}

export interface Anexo {
  anexo_id: string;
  descricao_visual: string;
  hash_perceptual?: string | null;
  exif_data_captura?: string | null;
  exif_software?: string | null;
}

export interface Sinal {
  tipo: string;
  descricao: string;
  anexo_id?: string | null;
}

export interface Veredicto {
  suspeita: boolean;
  sinais: Sinal[];
  custo_aceitar_falso_rs: number;
  custo_sinalizar_verdadeiro_rs: number;
  justificativa: string;
}

export interface Decisao {
  resultado: string;
  regra: string;
  motivo: string;
  aprovador_sugerido?: string | null;
  acoes_obrigatorias?: string[];
}

export interface RegistroAcao {
  acao_id: string;
  conversation_id: string | null;
  order_id: string | null;
  data_hora: string;
  sistema: string;
  acao: string;
  valor_rs: number;
  executado_por: string;
  aprovado_por: string | null;
  referencia_sistema: string;
}

export interface Pedido {
  order_id: string;
  marca?: string;
  valor?: number;
  status_entrega?: string;
  data_entrega?: string | null;
  itens?: { item_id: string; descricao: string; texto_personalizacao?: string | null }[];
}

export interface Caso {
  conversa: ItemFila;
  mensagens: Mensagem[];
  pedido: Pedido | null;
  anexos: Anexo[];
  veredicto: Veredicto | null;
  decisao: Decisao | null;
  acoes: RegistroAcao[];
  resposta_ao_cliente: string | null;
}

export type TipoCanal = "aviso" | "aprovacao" | "suspeita" | "escalacao";

export interface MensagemCanal {
  id: string;
  tipo: TipoCanal;
  para: string | null;
  texto: string;
  conversation_id: string | null;
  aprovacao_id?: string | null;
  estado?: string | null;
  solicitado_por?: string | null;
  suspeita_id?: string | null;
  prazo?: string | null;
  sinalizado_por?: string | null;
}

/** `GET /api/suspeitas`: suspeitas pendentes de decisão do supervisor. */
export interface SuspeitaPendente {
  suspeita_id: string;
  conversation_id: string | null;
  order_id: string | null;
  acao_proposta: string;
  valor_rs: number;
  sinais: unknown[];
  sinalizado_por: string | null;
  sinalizada_em: string | null;
  prazo: string | null;
  estado: string;
}

/** Conversa do histórico com foto, para o replay da verificação de evidência. */
export interface ItemReplay {
  conversation_id: string;
  order_id: string | null;
  marca?: string;
  canal?: string;
  assunto?: string;
  data_abertura?: string;
  [extra: string]: unknown;
}

export interface Placar {
  resolvidas_sozinho: number;
  aguardando_aprovacao: number;
  aguardando_cliente?: number;
  suspeitas: number;
  escaladas: number;
  valor_executado_rs: number;
  custo_evitado_rs: number;
}

export interface EventoApi {
  tipo: string;
  payload: unknown;
}

/** Payload do evento SSE `leitura`: quantas conversas o leitor já leu. */
export interface ProgressoLeitura {
  lidas: number;
  total: number;
}

/** Padrão de causa comum detectado pelo agente analista (`/api/analista/padroes`). */
export interface PadraoAnalista {
  tipo: string;
  fator: string;
  escopo: string[];
  evidencia: Record<string, unknown>;
  conversation_ids?: string[];
}

/** Resposta de `POST /api/analista/padroes/{tipo}/tratar`. */
export interface ResultadoTratamento {
  padrao: PadraoAnalista | null;
  incidente: ({ incidente_id?: string } & Record<string, unknown>) | null;
  notificacoes: unknown[];
  sem_consentimento: string[];
  adiados: string[];
  aviso_ao_time: unknown;
  detalhes: Record<string, unknown>;
  ja_tratado: boolean;
}

/** Alerta do vigia (SLA ou lembrete de aprovação). Campos variam; `texto` sempre vem. */
export interface AlertaVigia {
  texto: string;
  para?: string | null;
  conversation_id?: string | null;
  aprovacao_id?: string | null;
  [extra: string]: unknown;
}

/** `GET /api/vigia/alertas`: lista simples ou agrupada por tipo (ex.: {sla, aprovacoes}). */
export type RespostaVigia = AlertaVigia[] | Record<string, AlertaVigia[] | unknown>;
