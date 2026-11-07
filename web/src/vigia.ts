// Exibição dos alertas do vigia (HG-20/HG-21) como avisos no canal do time.
// Quem decide o que é alerta é o backend; aqui só mudamos o formato.
import type { AlertaVigia, MensagemCanal, RespostaVigia } from "./api/tipos";

const ehAlerta = (v: unknown): v is AlertaVigia =>
  typeof v === "object" && v !== null && typeof (v as AlertaVigia).texto === "string";

export function alertasComoMensagens(resp: RespostaVigia | null | undefined): MensagemCanal[] {
  if (!resp) return [];
  const lista: unknown[] = Array.isArray(resp)
    ? resp
    : Object.values(resp).flatMap((v) => (Array.isArray(v) ? v : []));
  return lista.filter(ehAlerta).map((a, i) => ({
    id: `vigia-${a.conversation_id ?? a.aprovacao_id ?? "x"}-${i}`,
    tipo: "aviso",
    para: a.para ?? null,
    texto: a.texto,
    conversation_id: a.conversation_id ?? null,
  }));
}

/** Acrescenta os avisos do vigia que o canal ainda não mostra (mesmo texto = mesmo aviso). */
export function juntarCanal(canal: MensagemCanal[], vigia: MensagemCanal[]): MensagemCanal[] {
  const vistos = new Set(canal.map((m) => m.texto));
  return [...canal, ...vigia.filter((m) => !vistos.has(m.texto))];
}
