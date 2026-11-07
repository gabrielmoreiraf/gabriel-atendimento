import "@fontsource/poppins/400.css";
import "@fontsource/poppins/500.css";
import "@fontsource/poppins/600.css";
import "@fontsource/poppins/700.css";
import "@fontsource/poppins/800.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "@fontsource/ibm-plex-mono/600.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { type Api, apiHttp, assinarEventos } from "./api/cliente";
import "./index.css";
import { Landing } from "./landing/Landing";
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

const raiz = document.getElementById("root");

// "/" é a landing do FIO; "/app" (e qualquer subcaminho) é a ferramenta.
if (raiz && !location.pathname.startsWith("/app")) {
  createRoot(raiz).render(
    <StrictMode>
      <Landing />
    </StrictMode>,
  );
} else {
  escolherApi().then(({ api, modo }) => montarApp(api, modo));
}

function montarApp(api: Api, modo: "api" | "mock") {
  if (!raiz) return;
  createRoot(raiz).render(
    <StrictMode>
      <App api={api} modo={modo} assinar={modo === "api" ? assinarEventos : semEventos} />
    </StrictMode>,
  );
}
