import "@testing-library/jest-dom/vitest";

// O jsdom não tem ResizeObserver nem Element.animate, que o PillNav (React Bits) usa.
if (!("ResizeObserver" in globalThis)) {
  class ResizeObserverDeTeste {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  (globalThis as { ResizeObserver?: unknown }).ResizeObserver = ResizeObserverDeTeste;
}
if (!Element.prototype.animate) {
  Element.prototype.animate = function animateDeTeste() {
    return { cancel() {}, finish() {}, onfinish: null } as unknown as Animation;
  };
}
