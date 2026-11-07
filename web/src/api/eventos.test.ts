import { afterEach, describe, expect, it, vi } from "vitest";
import { assinarEventos } from "./cliente";

class FonteFalsa {
  static ultima: FonteFalsa;
  onmessage: ((e: { data: string }) => void) | null = null;
  url: string;
  constructor(url: string) {
    this.url = url;
    FonteFalsa.ultima = this;
  }
  addEventListener() {}
  close() {}
  emitir(corpo: unknown) {
    this.onmessage?.({ data: JSON.stringify(corpo) });
  }
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("assinarEventos", () => {
  it("test_HP_09_leitura_chega_na_hora_com_o_progresso", () => {
    vi.stubGlobal("EventSource", FonteFalsa);
    const aoEvento = vi.fn();
    assinarEventos(aoEvento);
    FonteFalsa.ultima.emitir({ tipo: "leitura", payload: { lidas: 23, total: 65 } });
    expect(aoEvento).toHaveBeenCalledWith({ tipo: "leitura", payload: { lidas: 23, total: 65 } });
  });

  it("test_HP_09_rajada_de_acoes_vira_uma_recarga", () => {
    vi.useFakeTimers();
    vi.stubGlobal("EventSource", FonteFalsa);
    const aoEvento = vi.fn();
    assinarEventos(aoEvento);
    for (let i = 0; i < 20; i++) FonteFalsa.ultima.emitir({ tipo: "acao", payload: {} });
    expect(aoEvento).not.toHaveBeenCalled();
    vi.advanceTimersByTime(300);
    expect(aoEvento).toHaveBeenCalledOnce();
    expect(aoEvento).toHaveBeenCalledWith();
  });
});
