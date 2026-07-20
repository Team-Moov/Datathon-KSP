import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig, loadEnv } from "vite"

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "")
  // 8090, not 8000, by default — something else commonly owns 127.0.0.1:8000
  // on a dev machine (see backend/docker-compose.yml for the full story).
  // Override via VITE_API_PROXY_TARGET in frontend/.env when the backend runs
  // somewhere else — never hardcoded past this one fallback.
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || "http://localhost:8090"

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      proxy: {
        "/api": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
