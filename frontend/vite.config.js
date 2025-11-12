import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { writeFileSync } from 'fs'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'

// Get __dirname equivalent in ESM
const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

// Load env vars from .env.development for test environment
const testEnv = loadEnv('development', process.cwd(), '')

const withFallback = (value, fallback) => (value !== undefined && value !== '' ? value : fallback)

// Generate unique build hash for cache busting
const BUILD_HASH = process.env.VITE_CONFIG_HASH || Date.now().toString()

// Custom plugin to preserve runtime config.js (generated at container start)
function runtimeConfigPlugin() {
  return {
    name: 'runtime-config',
    resolveId(id) {
      // Mark /config.js as external so Vite doesn't try to bundle it
      // (it's generated at Docker container start time)
      if (id === '/config.js' || id.startsWith('/config.js?')) {
        return { id, external: true }
      }
    },
    transformIndexHtml(html) {
      // Inject the /config.js script tag with cache-busting hash
      // (it's marked external so Vite won't bundle it, but we need the tag in HTML)
      if (!html.includes('/config.js')) {
        return html.replace(
          '</title>',
          `</title>\n    <script type="module" src="/config.js?v=${BUILD_HASH}"></script>`
        )
      }
      return html
    },
    writeBundle() {
      // Write build hash to a file for Docker entrypoint to read
      const hashFile = join(__dirname, 'dist', '.build-hash')
      writeFileSync(hashFile, BUILD_HASH)
      console.log(`✓ Build hash ${BUILD_HASH} written to ${hashFile}`)
    }
  }
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [runtimeConfigPlugin(), react()],
  // Note: mqtt v5+ works directly in browsers, no alias needed
  define: {
    __BUILD_TIMESTAMP__: JSON.stringify(new Date().toISOString()),
  },
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: './src/__tests__/setup.js',
    env: {
      // Load from .env.development to match actual dev environment
      VITE_API_BASE_URL: withFallback(testEnv.VITE_API_BASE_URL, 'http://localhost:8000'),
      VITE_API_TIMEOUT_MS: withFallback(testEnv.VITE_API_TIMEOUT_MS, '35000'),
      VITE_MQTT_WS_URL: withFallback(testEnv.VITE_MQTT_WS_URL, 'ws://localhost:9001'),
    },
  },
})
