/** Junta chamadas em rajada numa só, `ms` depois da última (debounce). */
export function agrupar(fn: () => void, ms: number): () => void {
  let timer: ReturnType<typeof setTimeout> | undefined;
  return () => {
    clearTimeout(timer);
    timer = setTimeout(fn, ms);
  };
}
