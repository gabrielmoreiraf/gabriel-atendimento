import { afterEach, describe, expect, it, vi } from "vitest";
import { agrupar } from "./agrupar";

afterEach(() => vi.useRealTimers());

describe("agrupar", () => {
  it("test_HP_09_rajada_de_eventos_sse_vira_uma_recarga_so", () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const g = agrupar(fn, 200);
    for (let i = 0; i < 50; i++) g();
    expect(fn).not.toHaveBeenCalled();
    vi.advanceTimersByTime(200);
    expect(fn).toHaveBeenCalledOnce();
  });
});
