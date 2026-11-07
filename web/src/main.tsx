import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { type Api, apiHttp, assinarEventos } from "./api/cliente";
import "./index.css";
import { criarApiMock } from "./mocks/apiMock";
import { comRotasDeReserva } from "./mocks/replayReserva";

/** Usa a API real se `/api/fila` responder; senão, mocks locais (ou force com ?mock). */
async function escolherApi(): Promise<{ api: Api; modo: "api" | "mock" }> {
  if (new URLSearchParams(location.search).has("mock"))
    return { api: criarApiMock(), modo: "mock" };
  try {
    // sonda com tempo limite: backend reiniciando não pode deixar a tela em branco
    const resp = await fetch("/api/fila", { signal: AbortSignal.timeout(3000) });
    if (!resp.ok) throw new Error(String(resp.status));
    return { api: comRotasDeReserva(apiHttp, criarApiMock()), modo: "api" };
  } catch {
    return { api: criarApiMock(), modo: "mock" };
  }
}

const semEventos = () => () => {};

escolherApi().then(({ api, modo }) => {
  const raiz = document.getElementById("root");
  if (!raiz) return;
  createRoot(raiz).render(
    <StrictMode>
      <App api={api} modo={modo} assinar={modo === "api" ? assinarEventos : semEventos} />
    </StrictMode>,
  );
});
