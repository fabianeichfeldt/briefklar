import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// The browser always calls same-origin /api, so phones on the LAN only need port 5173.
// API_TARGET: Prism mock by default, e.g. API_TARGET=http://localhost:8000 for the FastAPI backend.
const API_TARGET = process.env.API_TARGET ?? 'http://127.0.0.1:4010'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,
    proxy: {
      '/api': { target: API_TARGET, changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, '') },
    },
  },
})
