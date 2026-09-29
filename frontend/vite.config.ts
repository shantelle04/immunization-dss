import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The API is proxied so the browser sees one origin: the refresh cookie and CSRF token stay same-site.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
