// Rotas que outros workers ainda estão plugando (replay, analista, vigia, reiniciar): enquanto a API
// devolver 404, a tela usa o mock. Qualquer outro erro da API aparece na tela.
import { type Api, ErroApi } from "../api/cliente";

const rotaAusente = (e: unknown) => e instanceof ErroApi && e.status === 404;

const ROTAS_NOVAS = [
  "casosReplay",
  "processarReplay",
  "padroes",
  "tratarPadrao",
  "alertasVigia",
  "rodarVigia",
  "suspeitas",
  "decidirSuspeita",
  "reiniciarDemo",
] as const;

export function comRotasDeReserva(real: Api, reserva: Api): Api {
  const api: Api = { ...real };
  for (const nome of ROTAS_NOVAS) {
    const doReal = real[nome] as (...a: unknown[]) => Promise<unknown>;
    const daReserva = reserva[nome] as (...a: unknown[]) => Promise<unknown>;
    (api as unknown as Record<string, unknown>)[nome] = (...args: unknown[]) =>
      doReal(...args).catch((e) => {
        if (rotaAusente(e)) return daReserva(...args);
        throw e;
      });
  }
  return api;
}
