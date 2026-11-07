// Vite da demo com o proxy /api apontando para outro backend (padrão :8010), sem editar web/.
// Uso: pnpm --dir web exec vite --config ../e2e/vite.e2e.config.mjs --port 5199 --strictPort
import { fileURLToPath } from "node:url";
import base from "../web/vite.config.ts";

const alvo = process.env.E2E_API || "http://localhost:8010";

export default {
  ...base,
  root: fileURLToPath(new URL("../web", import.meta.url)),
  server: { ...base.server, proxy: { "/api": alvo } },
};
