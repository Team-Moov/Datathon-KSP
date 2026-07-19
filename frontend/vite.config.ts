import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      // Backend published on host port 8090 (backend/docker-compose.yml) —
      // not 8000, which may already be owned by another local service.
      "/api": {
        target: "http://localhost:8090",
        changeOrigin: true,
      },
    },
  },
})
