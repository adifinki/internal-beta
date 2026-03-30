import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/api/market-data": {
        target: "http://127.0.0.1:8001",
        rewrite: (path) => path.replace(/^\/api\/market-data/, ""),
      },
      "/api/portfolio": {
        target: "http://127.0.0.1:8002",
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
      "/api/risk": {
        target: "http://127.0.0.1:8003",
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
