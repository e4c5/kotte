import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// Proxy target for API requests (configurable for Docker: use http://backend:8000)
const apiProxyTarget = process.env.VITE_PROXY_TARGET || 'http://localhost:8000'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      // `@neo4j-cypher/codemirror` package.json "exports" omit this module;
      // we need `getStateEditorSupport` to call `setSchema` on the React-mounted editor.
      'neo4j-cypher-cm-state-selectors': path.resolve(
        __dirname,
        'node_modules/@neo4j-cypher/codemirror/es/cypher-state-selectors.js'
      ),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['src/test/setup.ts'],
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
