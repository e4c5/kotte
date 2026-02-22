import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxy target for API requests (configurable for Docker: use http://backend:8000)
const apiProxyTarget = process.env.VITE_PROXY_TARGET || 'http://localhost:8000'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    exclude: ['**/node_modules/**', '**/e2e/**'],
    passWithNoTests: true,
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
})

