// Formatação de exibição apenas (sem regra de negócio).
import type { EstadoConversa } from "./api/tipos";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export const formatarRs = (valor: number | null | undefined): string =>
  valor == null ? "—" : brl.format(valor);

/** "2026-11-02T08:00:03-03:00" ou "2026-11-02 08:00:03" → "02/11 08:00:03". */
export function formatarDataHora(texto: string | null | undefined): string {
  if (!texto) return "—";
  const m = texto.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)/);
  return m ? `${m[3]}/${m[2]} ${m[4]}` : texto;
}

export const ROTULO_ESTADO: Record<EstadoConversa, string> = {
  aberta: "Aberta",
  resolvida: "Resolvida",
  aguardando_aprovacao: "Aguardando aprovação",
  aguardando_cliente: "Aguardando cliente",
  suspeita: "Suspeita",
  escalada: "Escalada",
};

export const rotuloEstado = (estado: string): string =>
  ROTULO_ESTADO[estado as EstadoConversa] ?? estado;

/** "Agora" do projeto (contratos.AGORA): o vigia nunca usa o relógio do sistema. */
export const AGORA_ISO = "2026-11-02T08:00:00";
/** Horário para onde a demo avança o relógio do vigia (o backend decide os alertas). */
export const RELOGIO_0820_ISO = "2026-11-02T08:20:00";
