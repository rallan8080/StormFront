import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Required for HMR over a Docker bind mount on Windows — native fs events
    // don't always propagate, so fall back to polling.
    watch: {
      usePolling: true,
      interval: 200,
    },
  },
})
