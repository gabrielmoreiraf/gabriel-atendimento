import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { assinarEventos } from "./cliente";

class FonteFalsa {
  static todas: FonteFalsa[] = [];
  static get ultima() {
    return FonteFalsa.todas[FonteFalsa.todas.length - 1];
  }
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string; lastEventId: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  fechada = false;
  url: string;
  constructor(url: string) {
    this.url = url;
    FonteFalsa.todas.push(this);
  }
  addEventListener() {}
  close() {
    this.fechada = true;
  }
  emitir(corpo: unknown, id = "") {
    this.onmessage?.({ data: JSON.stringify(corpo), lastEventId: id });
  }
}

beforeEach(() => {
  FonteFalsa.todas = [];
  vi.stubGlobal("EventSource", FonteFalsa);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("assinarEventos", () => {
  it("test_HP_09_leitura_chega_na_hora_com_o_progresso", () => {
    const aoEvento = vi.fn();
    assinarEventos(aoEvento);
    FonteFalsa.ultima.emitir({ tipo: "leitura", payload: { lidas: 23, total: 65 } });
    expect(aoEvento).toHaveBeenCalledWith({ tipo: "leitura", payload: { lidas: 23, total: 65 } });
  });

  it("test_HP_09_rajada_de_acoes_vira_uma_recarga", () => {
    vi.useFakeTimers();
    const aoEvento = vi.fn();
    assinarEventos(aoEvento);
    for (let i = 0; i < 20; i++) FonteFalsa.ultima.emitir({ tipo: "acao", payload: {} }, String(i));
    expect(aoEvento).not.toHaveBeenCalled();
    vi.advanceTimersByTime(300);
    expect(aoEvento).toHaveBeenCalledOnce();
    expect(aoEvento).toHaveBeenCalledWith();
  });

  it("test_HG_13_stream_fechado_reconecta_com_desde_do_ultimo_id", () => {
    vi.useFakeTimers();
    assinarEventos(vi.fn());
    expect(FonteFalsa.ultima.url).toBe("/api/eventos");
    FonteFalsa.ultima.emitir({ tipo: "acao", payload: {} }, "41");
    FonteFalsa.ultima.onerror?.();
    expect(FonteFalsa.todas[0].fechada).toBe(true);
    vi.advanceTimersByTime(30_000);
    expect(FonteFalsa.todas.length).toBeGreaterThan(1);
    expect(FonteFalsa.ultima.url).toBe("/api/eventos?desde=41");
  });

  it("test_HG_13_evento_repetido_na_reconexao_e_ignorado", () => {
    vi.useFakeTimers();
    const aoEvento = vi.fn();
    assinarEventos(aoEvento);
    FonteFalsa.ultima.emitir({ tipo: "leitura", payload: { lidas: 1, total: 2 } }, "7");
    FonteFalsa.ultima.onerror?.();
    vi.advanceTimersByTime(30_000);
    aoEvento.mockClear();
    FonteFalsa.ultima.onopen?.();
    FonteFalsa.ultima.emitir({ tipo: "leitura", payload: { lidas: 1, total: 2 } }, "7");
    expect(aoEvento).not.toHaveBeenCalled();
    FonteFalsa.ultima.emitir({ tipo: "leitura", payload: { lidas: 2, total: 2 } }, "8");
    expect(aoEvento).toHaveBeenCalledWith({ tipo: "leitura", payload: { lidas: 2, total: 2 } });
  });

  it("test_HG_13_sem_stream_cai_para_polling_e_para_quando_volta", () => {
    vi.useFakeTimers();
    const aoEvento = vi.fn();
    assinarEventos(aoEvento, { pollingMs: 5000 });
    FonteFalsa.ultima.onerror?.();
    aoEvento.mockClear();
    vi.advanceTimersByTime(5000);
    expect(aoEvento.mock.calls.length).toBeGreaterThanOrEqual(1);
    // o stream volta: o polling para
    vi.advanceTimersByTime(30_000);
    FonteFalsa.ultima.onopen?.();
    aoEvento.mockClear();
    vi.advanceTimersByTime(20_000);
    expect(aoEvento).not.toHaveBeenCalled();
  });

  it("test_HG_13_cancelar_fecha_tudo", () => {
    vi.useFakeTimers();
    const aoEvento = vi.fn();
    const cancelar = assinarEventos(aoEvento, { pollingMs: 5000 });
    FonteFalsa.ultima.onerror?.();
    cancelar();
    const total = FonteFalsa.todas.length;
    aoEvento.mockClear();
    vi.advanceTimersByTime(60_000);
    expect(aoEvento).not.toHaveBeenCalled();
    expect(FonteFalsa.todas.length).toBe(total);
  });
});
