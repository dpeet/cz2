# Mountainstat

React-based virtual thermostat for the Mountain House. Connects to a Python
cz2 backend API and local MQTT broker for real-time HVAC control and
monitoring of the Carrier ComfortZone II system.

## Setup

### Install Dependencies
```bash
npm install
```

### Environment Configuration

Vite automatically loads environment files based on the build mode:
- **Development** (`npm run dev`): Uses `.env.development`
- **Production** (`npm run build`): Uses `.env.production`
- **Override**: Create `.env.local` to override both (not committed to git)

Copy the example file to get started:
```bash
cp .env.example .env.local
```

**Required Environment Variables:**
- `VITE_API_BASE_URL` - Backend API URL (e.g., `http://localhost:8000`)
- `VITE_MQTT_WS_URL` - MQTT WebSocket URL (e.g., `ws://localhost:9001`)
- `VITE_API_TIMEOUT_MS` - API timeout in milliseconds (see .env files)

See `.env.example` for development and production configurations.

## Development

### Start Development Server
```bash
npm run dev
```

Development server runs on `http://localhost:5173` with network access
enabled (accessible from LAN via Tailscale IP).

### Run Tests
```bash
npm test          # Run all tests
npm run test:ui   # Run tests with UI
```

## Production Build

### Build for Deployment
```bash
npm run build
```

Production build uses `.env.production` settings and outputs to `dist/`
directory for Caddy/Home Assistant deployment.

### Preview Production Build
```bash
npm run preview
```
