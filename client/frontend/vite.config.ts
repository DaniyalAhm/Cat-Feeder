import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev, proxy /api -> backend :6607 to avoid CORS.
// In prod (python http.server serving dist/), set VITE_API_URL
// e.g. VITE_API_URL=http://localhost:6607 npm run build,
// otherwise same-origin /api is used.
export default defineConfig({
  plugins: [react()],
  base: './',
  server: {
    host: true,
    port: 6606,
    allowedHosts:"toddheadquarters",
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY ?? 'http://127.0.0.1:6607',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
