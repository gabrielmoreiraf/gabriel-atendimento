/* Adaptado de MicroKit UI (hover-glide-cards), licença MIT: ver LICENSE-microkit.txt.
 * Mudanças: itens por prop (sem lucide-react), cartões maiores e cores do FIO no CSS. */
import "./cartoes-deslizantes.css";

import { type ReactNode, useEffect, useRef } from "react";

export interface CartaoItem {
  nome: string;
  detalhe: string;
  marca: ReactNode;
}

export function CartoesDeslizantes({ itens, rotulo }: { itens: CartaoItem[]; rotulo: string }) {
  const hostRef = useRef<HTMLUListElement>(null);
  const layerRef = useRef<HTMLSpanElement>(null);
  const glideRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const host = hostRef.current;
    const layer = layerRef.current;
    const glide = glideRef.current;
    if (!host || !layer || !glide) return;

    const tiles = Array.from(host.querySelectorAll("[data-glide-card]"));
    const controller = new AbortController();
    const { signal } = controller;
    let active = -1;
    let shown = false;

    // O destaque só aparece pelo formato dos cartões: ao cruzar o vão, ele esvazia um e enche o próximo.
    const drawMask = () => {
      const bounds = host.getBoundingClientRect();
      const shapes = tiles
        .map((tile) => {
          const rect = tile.getBoundingClientRect();
          const x = rect.left - bounds.left + host.scrollLeft - host.clientLeft;
          const y = rect.top - bounds.top + host.scrollTop - host.clientTop;
          const radius = Number.parseFloat(getComputedStyle(tile).borderTopLeftRadius) || 0;
          return `<rect x="${x}" y="${y}" width="${rect.width}" height="${rect.height}" rx="${radius}"/>`;
        })
        .join("");
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${host.scrollWidth}" height="${host.scrollHeight}">${shapes}</svg>`;
      const image = `url("data:image/svg+xml,${encodeURIComponent(svg)}")`;
      layer.style.width = `${host.scrollWidth}px`;
      layer.style.height = `${host.scrollHeight}px`;
      layer.style.setProperty("mask-image", image);
      layer.style.setProperty("-webkit-mask-image", image);
    };

    const place = () => {
      const tile = tiles[active];
      if (!tile) return;
      const bounds = host.getBoundingClientRect();
      const rect = tile.getBoundingClientRect();
      const x = rect.left - bounds.left + host.scrollLeft - host.clientLeft;
      const y = rect.top - bounds.top + host.scrollTop - host.clientTop;
      if (!shown) glide.style.transition = "opacity 180ms ease";
      glide.style.transform = `translate(${x}px, ${y}px)`;
      glide.style.width = `${rect.width}px`;
      glide.style.height = `${rect.height}px`;
      if (!shown) {
        void glide.offsetWidth;
        glide.style.transition = "";
        shown = true;
      }
      glide.dataset.visible = "";
    };

    const hide = () => {
      shown = false;
      delete glide.dataset.visible;
    };

    for (const type of ["pointerover", "focusin"]) {
      host.addEventListener(
        type,
        (event) => {
          const tile =
            event.target instanceof Element ? event.target.closest("[data-glide-card]") : null;
          const index = tile ? tiles.indexOf(tile) : -1;
          if (index < 0) return;
          if (!shown || index !== active) drawMask();
          active = index;
          place();
        },
        { signal },
      );
    }
    host.addEventListener("pointerleave", hide, { signal });
    host.addEventListener(
      "focusout",
      (event) => {
        const inside = event.relatedTarget instanceof Node && host.contains(event.relatedTarget);
        if (!inside && !host.matches(":hover")) hide();
      },
      { signal },
    );

    const reflow =
      typeof ResizeObserver !== "undefined"
        ? new ResizeObserver(() => {
            if (!shown) return;
            drawMask();
            place();
          })
        : null;
    reflow?.observe(host);

    return () => {
      controller.abort();
      reflow?.disconnect();
    };
  }, []);

  return (
    <ul className="hover-glide-cards" aria-label={rotulo} ref={hostRef}>
      <span className="hover-glide-cards__layer" ref={layerRef} aria-hidden="true">
        <span className="hover-glide-cards__glide" ref={glideRef} />
      </span>
      {itens.map((item) => (
        <li className="hover-glide-card" data-glide-card="" key={item.nome}>
          <span className="hover-glide-card__mark">{item.marca}</span>
          <span className="hover-glide-card__name">{item.nome}</span>
          <span className="hover-glide-card__detail">{item.detalhe}</span>
        </li>
      ))}
    </ul>
  );
}
