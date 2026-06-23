import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The SPA is a thin client of the FastAPI JSON API plus the server-side OAuth
// redirect flow. In dev we proxy both to the backend (run it on :8000) so the
// browser stays same-origin — the session cookie and the 401 -> /auth/login
// handoff behave exactly as they will in production (where FastAPI serves the
// built assets directly; see frontend phase F-H).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/healthz': 'http://localhost:8000',
    },
  },
})
