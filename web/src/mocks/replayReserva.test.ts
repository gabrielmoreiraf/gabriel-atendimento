import { describe, expect, it } from "vitest";
import { type Api, ErroApi } from "../api/cliente";
import { criarApiMock } from "./apiMock";
import { comRotasDeReserva } from "./replayReserva";

const apiSemReplay = (): Api => ({
  ...criarApiMock(),
  casosReplay: async () => {
    throw new ErroApi(404, "Not Found");
  },
  processarReplay: async () => {
    throw new ErroApi(404, "Not Found");
  },
});

describe("comRotasDeReserva", () => {
  it("test_EC_16_rota_de_replay_ausente_usa_os_casos_mock", async () => {
    const api = comRotasDeReserva(apiSemReplay(), criarApiMock());
    const casos = await api.casosReplay();
    expect(casos.length).toBeGreaterThan(0);
    const caso = await api.processarReplay(casos[0].conversation_id);
    expect(caso.veredicto?.sinais.length).toBeGreaterThan(0);
  });

  it("test_EC_16_outros_erros_da_api_nao_sao_escondidos", async () => {
    const real = {
      ...criarApiMock(),
      casosReplay: async () => Promise.reject(new ErroApi(500, "quebrou")),
    };
    await expect(comRotasDeReserva(real, criarApiMock()).casosReplay()).rejects.toThrow("quebrou");
  });
});

describe("comRotasDeReserva: analista e vigia", () => {
  it("test_HG_19_analista_sem_rota_usa_mock", async () => {
    const real: Api = {
      ...criarApiMock(),
      padroes: async () => {
        throw new ErroApi(404, "Not Found");
      },
    };
    const padroes = await comRotasDeReserva(real, criarApiMock()).padroes();
    expect(padroes.length).toBeGreaterThan(0);
  });
});
