import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// The browser always calls same-origin /api, so phones on the LAN only need port 5173.
// API_TARGET: the FastAPI backend by default; API_TARGET=http://127.0.0.1:4010 for the Prism mock.
const API_TARGET = process.env.API_TARGET ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,
    proxy: {
      '/api': { target: API_TARGET, changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, '') },
    },
  },
})
