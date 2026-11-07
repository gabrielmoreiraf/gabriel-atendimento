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
  // Local: uma tentativa curta. Publicado: a primeira chamada acorda a função do Vercel e pode
  // levar alguns segundos, então tenta de novo com mais paciência antes de cair nos exemplos.
  const local = ["localhost", "127.0.0.1"].includes(location.hostname);
  for (const limite of local ? [3000] : [8000, 15000, 20000]) {
    try {
      const resp = await fetch("/api/fila", { signal: AbortSignal.timeout(limite) });
      if (resp.ok) return { api: comRotasDeReserva(apiHttp, criarApiMock()), modo: "api" };
    } catch {
      // tenta de novo com um limite maior
    }
  }
  return { api: criarApiMock(), modo: "mock" };
}

const semEventos = () => () => {};

const raiz = document.getElementById("root");

// "/" é a landing do Gabriel; "/app" (e qualquer subcaminho) é a ferramenta.
if (raiz && !location.pathname.startsWith("/app")) {
  createRoot(raiz).render(
    <StrictMode>
      <Landing />
    </StrictMode>,
  );
} else {
  const raizReact = raiz ? createRoot(raiz) : null;
  raizReact?.render(<p className="abrindo">Abrindo o Gabriel…</p>);
  escolherApi().then(({ api, modo }) => montarApp(raizReact, api, modo));
}

function montarApp(
  raizReact: ReturnType<typeof createRoot> | null,
  api: Api,
  modo: "api" | "mock",
) {
  if (!raizReact) return;
  raizReact.render(
    <StrictMode>
      <App api={api} modo={modo} assinar={modo === "api" ? assinarEventos : semEventos} />
    </StrictMode>,
  );
}
