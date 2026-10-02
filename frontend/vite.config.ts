import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The API is proxied so the browser sees one origin: the refresh cookie and CSRF token stay same-site.
// The end-to-end runner points both at its own backend through these two variables.
const api = process.env.IMMDSS_API ?? "http://127.0.0.1:8000";
const port = Number(process.env.IMMDSS_WEB_PORT ?? 5173);

export default defineConfig({
  plugins: [react()],
  server: { port, strictPort: true, proxy: { "/api": api } },
  preview: { port: 4173, strictPort: true, proxy: { "/api": api } },
});
