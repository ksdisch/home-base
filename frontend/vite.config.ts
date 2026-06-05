import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// One configurable base for the API: the dev server proxies /api -> FastAPI on :8000.
// The frontend only ever talks to "/api" (see src/api/client.ts), so there is no scattered URL.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true, // expose on LAN so a phone on the same network can reach the hub
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
