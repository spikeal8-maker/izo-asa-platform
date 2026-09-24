import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const dockerDev = process.env.IZO_VITE_DOCKER === 'true'
const hmrClientPort = Number(process.env.IZO_VITE_HMR_CLIENT_PORT || 0)
const apiTarget = process.env.IZO_VITE_API_TARGET ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: dockerDev ? '0.0.0.0' : '127.0.0.1',
    watch: dockerDev ? { usePolling: true, interval: 200 } : undefined,
    hmr: dockerDev && hmrClientPort ? { clientPort: hmrClientPort } : undefined,
    proxy: { '/api': { target: apiTarget, changeOrigin: false } },
  },
})
