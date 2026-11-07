/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Só para `pnpm dev`: no Vercel a API está na mesma origem (/api) e não há proxy.
const alvoApi =
  process.env.FIO_API_URL ?? `http://127.0.0.1:${process.env.FIO_API_PORTA ?? "8000"}`;

export default defineConfig({
  plugins: [react()],
  server: {
    fs: { allow: [".."] },
    proxy: {
      "/api": alvoApi,
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
