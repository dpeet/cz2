# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mountainstat is a React-based virtual thermostat application for controlling a Carrier ComfortZone II HVAC system. It consumes MQTT snapshots from the existing Home Assistant Mosquitto broker and issues commands to the Python `cz2` backend API.

## Development Commands

```bash
# Install dependencies
npm install

# Start development server (includes --host flag for network access)
npm run dev

# Build for production (Home Assistant/Caddy deployment)
npm run build

# Preview production build
npm run preview

# Run tests
npm test

# Run tests with UI
npm run test:ui
```

**Note**: For development, connect using the Tailscale IP address as localhost SSH doesn't hot reload correctly.

## Architecture Overview

### Technology Stack
- **Frontend**: React 18 with functional components and hooks
- **Build Tool**: Vite 5 with npm (package-lock.json)
- **Language**: JavaScript (.jsx files)
- **Styling**: SCSS/Sass
- **Real-time Communication**: MQTT WebSocket via `mqtt` v5+ package
- **HTTP API**: Axios for Python cz2 backend (POST-based API)
- **State Management**: Local React state with hooks
- **Testing**: Vitest with @testing-library/react

### Key Components
- **App.jsx**: Main component handling MQTT connection and message parsing
- **System.jsx**: Primary UI component for thermostat controls and API interactions
- **apiService.js**: POST-based API client for backend communication
- **apiNormalizer.js**: Response normalization and control state logic
- **Main MQTT Topic**: `hvac/cz2` - Receives JSON thermostat data

### API Endpoints (Python cz2 Backend)
- `POST /system/mode` - Set system mode (heat/cool/auto/off)
- `POST /system/fan` - Set fan mode (auto/on)
- `POST /zones/{id}/temperature` - Set zone temperature setpoints
- `POST /zones/{id}/hold` - Enable/disable zone hold mode
- `POST /update` - Request HVAC status update

## Environment Configuration

Configuration via `.env` files (Vite auto-loads based on mode):
- `.env.development` - Local dev (http://localhost:8000, ws://localhost:9001)
- `.env.production` - Production (https://api.mtnhouse.casa, wss://mqtt.mtnhouse.casa)
- `.env.local` - Optional overrides (not committed to git)

Required variables:
- `VITE_API_BASE_URL` - Backend API URL
- `VITE_MQTT_WS_URL` - MQTT WebSocket URL
- `VITE_API_TIMEOUT_MS` - API timeout (default: 5000ms)

## Migration Status

This frontend has been migrated from Node-RED to the Python cz2 backend:
- ✓ API service layer (POST-based helpers in `apiService.js`)
- ✓ Response normalization via `apiNormalizer.js`
- ✓ Environment externalization (`.env.*` files + docs)
- ✓ MQTT client standardization (`mqtt` v5)
- ✓ Test coverage (Vitest + @testing-library/react)

## Known Issues

### Future Improvements
1. **Manual QA**: Document connection indicator + command success paths in README/checklist
2. **State Management**: Consolidate the remaining ad-hoc state into focused hooks
3. **Error UX**: Replace placeholder banner (`TODO (clarify)`) with toast/notification system
4. **Zone Flexibility**: Derive zone list dynamically from status metadata
5. **MQTT Resilience**: Add reconnect/backoff strategy around `mqtt` client

## Code Quality Guidelines

### State Updates
Continue using functional updates whenever state depends on previous values:
```javascript
setSystemFanMode(prevMode => prevMode === "Auto" ? "Always On" : "Auto");
```

### API + Normalisation
- Use the helpers exposed by `apiService.js` (`systemMode`, `systemFan`, etc.) to
  avoid duplicating Axios configuration.
- Immediately wrap responses with `normalizeStatus` and act on
  `shouldDisableControls` when mutating UI state.
- Error handlers should call `setError` and rely on the shared banner until the
  TODO notification system is implemented.

### Input Validation
Validate temperature inputs (45-80°F range) before sending to the backend:
```javascript
const isValidTemperature = temp => temp >= 45 && temp <= 80;
```

## Development Notes

- Test coverage available via Vitest (57 tests across 4 test files)
- The `src/json_response.js` file contains legacy mock data (may be removed)
- Build output is deployed to Home Assistant with Caddy reverse proxy
- Uses npm (package-lock.json) for dependency management
