import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // Note: mqtt v5+ works directly in browsers, no alias needed
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: './src/__tests__/setup.js',
    env: {
      VITE_API_BASE_URL: 'http://localhost:8000',
      VITE_API_TIMEOUT_MS: '5000',
      VITE_MQTT_WS_URL: 'ws://localhost:9001',
    },
  },
})
