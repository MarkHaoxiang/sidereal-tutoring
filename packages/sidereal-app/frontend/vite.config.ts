import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// No @types/node in this project; this config runs under Node regardless.
declare const process: { env: Record<string, string | undefined> };

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": "/src" },
  },
  server: {
    // Not VITE_-prefixed: a VITE_ var inlines into the bundle at build time,
    // and this is a dev-server-only proxy target.
    proxy: {
      "/api": {
        // `??` alone lets an empty-string env var through as a broken
        // target; treat blank/whitespace-only as unset too.
        target: process.env.SIDEREAL_API_PROXY?.trim() || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  // `vite preview` serves the production build; it needs the same /api proxy so
  // a local preview can talk to the backend the dev server also proxies to.
  preview: {
    proxy: {
      "/api": {
        target: process.env.SIDEREAL_API_PROXY?.trim() || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
