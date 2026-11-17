import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    outDir: "../packages/plynx/src/plynx/static",
    emptyOutDir: true,
  },
  server: {
    port: 3000,
    proxy: {
      "/api": "http://127.0.0.1:8080",
      "/runs": "http://127.0.0.1:8080",
      "/health": "http://127.0.0.1:8080",
    },
  },
});
