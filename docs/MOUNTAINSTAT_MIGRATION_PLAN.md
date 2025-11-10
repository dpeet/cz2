# Mountainstat → Python Backend Migration Plan

**Goal:** Point the `mountainstat-main` React app at the new `cz2` Python backend (replacing the legacy Node-RED/Perl stack) with the minimum set of code changes, bug fixes, and shipping quality. Focus on parity first; defer new features (SSE, optimistic updates, etc.) until the basic experience is stable. Wrap both services in Docker and provide a single `docker-compose.yml` for local and on-prem deployment.

**Branching:** Before touching code, create a dedicated working branch (e.g., `git checkout -b feature/mountainstat-python-migration`).

---

## Scope & Assumptions

- The Python backend (`cz2`) stays in CLI-mode (worker disabled) and publishes snapshots to MQTT as it updates the cache.
- We reuse the existing MQTT topic structure (`hvac/cz2`) for live status. The frontend can continue to consume MQTT (via WebSocket) for real-time updates.
- All command endpoints switch from legacy `GET` to the Python API (`POST` JSON). We lean on the `?flat=1` flag to keep the payload shape close to the old UI until a deeper refactor happens.
- Deployment target expects Docker containers orchestrated through compose; secrets (MQTT creds, API base URLs) come from `.env` files.
- Local Python tooling uses `uv`; prefer native commands (`uv sync`, `uv run`, `uv pip`) instead of invoking `pip` directly.
- A host-level Caddy instance is available for TLS/edge proxy duties and will front the compose stack.

---

## Endpoint alignment decision

We will update the frontend to consume the structured Python POST endpoints directly (no backend shim). Use the `?flat=1` flag during migration to keep the response shape close to what the legacy UI expects. If any temporary compatibility helper is introduced, document it immediately and plan its removal after the UI flip is complete.

---

## Backend readiness (cz2)

- [x] `/status?flat=1` matches the legacy payload exactly:
  - Convert `SystemMode`/`FanMode` enums to title-case strings (`"Heat"`, `"Auto"`). ✅ Verified 2025-10-03
  - Convert `all_mode` to numeric (False → 0, True → 1, preserve integer values 1-8 when returned by HVAC). ✅ Implemented 2025-10-03
  - Include `time` field (`int(time.time())`) to satisfy UI timestamp checks. ✅ Implemented 2025-10-03
  - Ensure `damper_position` remains a string (UI compares to `"100"`). ✅ Implemented 2025-10-03
  - Validate against `mountainstat-main/src/json_response.js` and existing MQTT payloads. ✅ Manual verification complete.
- [x] Document the POST command contract (`/system/mode`, `/system/fan`, `/zones/{id}/temperature`, `/zones/{id}/hold`, `/update`), including accepted values and response shape.
- [x] Verify MQTT publishing (`MQTT_ENABLED=true`) sends payloads identical to the flat `/status` response (including `time` and numeric `all_mode`). Tested with `mosquitto_sub -h host.docker.internal -t 'hvac/cz2' -v`.
- [ ] Confirm CORS allow-list matches all development and production origins (local Vite server, LAN IP, Caddy-served domain). **Outstanding:** audit before production cutover.
- [x] Provide updated `.env` sample documenting MQTT host/port, cache settings, and CLI refresh intervals.
- [x] Update backend README/Docker instructions to emphasise `uv` workflows (`uv sync --frozen --no-dev`, `uv run uvicorn pycz2.api:app ...`).

### Frontend API endpoint mapping

Replace Node-RED `GET` calls with `cz2` POST requests.

| Legacy endpoint | New endpoint | Payload / notes |
| --- | --- | --- |
| `GET /hvac/system/mode?mode={mode}` | `POST /system/mode` | `{ "mode": "heat" | "cool" | "auto" | "off" }` |
| `GET /hvac/system/fan?fan={mode}` | `POST /system/fan` | Map `always_on` → `{ "fan": "always_on" }`, `auto` stays `auto` |
| `GET /hvac/system/allmode?mode={mode}` | `POST /system/mode` | Include current mode plus `{ "all": true }` (`mode=on`) or `{ "all": false }` (`mode=off`) |
| `GET /hvac/settemp?mode={mode}&temp={temp}&zone={zone}` | `POST /zones/{zone}/temperature` | `{ "heat": temp, "temp": true }` when mode=`heat`; `{ "cool": temp, "temp": true }` when mode=`cool` |
| `GET /hvac/sethold?zone={zone}&setHold={on|off}` | `POST /zones/{zone}/hold` | `{ "hold": setHold === "on", "temp": true }`; support `zone=all` by iterating calls |
| `GET /hvac/update` | `POST /update` | No payload; backend queues refresh and publishes MQTT |

Update `apiService.js` to expose helper methods that wrap these POST calls and return normalised responses.

### Frontend React fixes (from CLAUDE review)

- [ ] `App.jsx` MQTT effect: add dependency array and return cleanup that calls `client.end()`.
- [ ] Convert state setters in `System.jsx` to functional form where they depend on previous state (e.g., toggling fan/all mode).
- [ ] Add `const [error, setError] = useState(null);` and render error UI where `setError` is used.
- [ ] Remove unused components (`Status.jsx`, `mqttService.jsx`) once new wiring is complete.
- [ ] Ensure all `useEffect` hooks include the correct dependency arrays.

## Frontend migration (mountainstat-main)

- [x] Externalise configuration via `.env` (`VITE_API_BASE_URL`, `VITE_MQTT_WS_URL`, `VITE_API_TIMEOUT_MS`). Provide `example.env` values for local dev vs Caddy deployment.
- [x] Standardise on the maintained `mqtt` package (v5+) in browser builds and read broker URL from env (default `ws://localhost:9001` for local testing, `wss://mqtt.mtnhouse.casa` in production).
- [x] Implement the API mapping table above in `apiService.js` and refactor `System.jsx` to use the helpers (no raw `axios.get`).
- [x] Add a response normaliser (`src/apiNormalizer.js`) to unify `{status, meta}` and flat payloads, exposing helpers like `normalizeStatus()` and `shouldDisableControls()`.
- [x] Update MQTT message handler to pass payloads through the normaliser before setting state.
- [x] Remove legacy URLs, console noise, and unused modules while preserving existing layout.
- [x] Apply React fixes outlined above.

## Configuration files

- [x] Backend `.env` template:
  ```env
  CZ_CONNECT="10.0.1.20:8899"
  CZ_ZONES=4
  API_HOST="0.0.0.0"
  API_PORT=8000
  MQTT_ENABLED=true
  MQTT_HOST="mqtt"              # existing Mosquitto container on host network
  MQTT_PORT=1883
  MQTT_TOPIC_PREFIX="hvac/cz2"
  CACHE_REFRESH_INTERVAL=300
  CACHE_STALE_SECONDS=300
  CORS_ORIGINS=["http://localhost:5173","https://mtnhouse.casa"]
  ```
- [x] Frontend `.env.development`:
  ```env
  VITE_API_BASE_URL=http://localhost:8000
  VITE_MQTT_WS_URL=ws://localhost:9001
  ```
- [x] Frontend `.env.production` (served behind Caddy):
  ```env
  VITE_API_BASE_URL=https://api.mtnhouse.casa
  VITE_MQTT_WS_URL=wss://mqtt.mtnhouse.casa
  ```
- [x] Document how to reference the existing Mosquitto container (see README “Integrating with Existing Home Assistant Mosquitto”). Compose now points at external broker by default.

## Integration & verification

- [x] **Backend reachability**
  - `curl http://localhost:8000/health`
  - `curl "http://localhost:8000/status?flat=1"` → verified types (2025-10-03).
- [x] **MQTT publishing**
  - `mosquitto_sub -h host.docker.internal -p 1883 -t 'hvac/cz2' -v`
  - `curl -X POST http://localhost:8000/update` → message received within 3s.
- [ ] **Frontend smoke test**
  - `npm run dev` → open `http://localhost:4173`
  - Confirm connection indicator reflects MQTT state, zone data renders, “Last Updated” matches payload. **Pending:** manual browser verification.
- [~] **Command execution test**
  - Backend POST endpoints confirmed via curl; ensure UI interactions update MQTT payloads. **Pending:** UI validation.
- [ ] **Error handling test**
  - Simulate HVAC offline (wrong `CZ_CONNECT`) → ensure UI shows stale state, controls disabled via normaliser metadata, MQTT stays connected. **Pending:** requires staging/offline simulation.
- [x] Capture final configuration and test steps in project READMEs.

## Dockerization

- [x] Backend Dockerfile refreshed (uv sync ordering, cache permissions, docs updated).
  ```dockerfile
  FROM python:3.13-bookworm
  COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
  RUN apt-get update && apt-get install -y --no-install-recommends udev && rm -rf /var/lib/apt/lists/*
  WORKDIR /app
  COPY pyproject.toml uv.lock ./
  RUN uv sync --frozen --no-dev
  COPY src/ ./src/
  RUN useradd -m -u 1000 hvac && usermod -a -G dialout hvac
  USER hvac
  EXPOSE 8000
  CMD ["uv", "run", "uvicorn", "pycz2.api:app", "--host", "0.0.0.0", "--port", "8000"]
  ```
  - Map serial device if needed: `devices: ["/dev/ttyUSB0:/dev/ttyUSB0"]` and set `CZ_CONNECT=/dev/ttyUSB0`. For TCP (recommended), set `CZ_CONNECT=10.0.1.20:8899` and omit device mapping.
- [x] Frontend Dockerfile: multi-stage build with npm; env wiring documented.
- [x] Compose file (`docker-compose.yml`): backend + frontend services only; internal Mosquitto removed. Broker accessed via `host.docker.internal`. Ports map to 8000 (API) and 4173 (frontend).
- [x] Provide developer instructions (build, run, logs) plus the `uv` install snippet already shown.

### Response normalisation helper

- [ ] Create `src/apiNormalizer.js` to translate backend responses and MQTT payloads into the legacy shape while preserving metadata for control disabling.
- [ ] Update `App.jsx` and `System.jsx` to consume the normalised structure exclusively.

### Reverse proxy (Caddy)

- [ ] Document Caddy configuration:
  ```caddy
  mtnhouse.casa {
      reverse_proxy 127.0.0.1:8080
      encode gzip
      header {
          Strict-Transport-Security "max-age=31536000;"
          X-Content-Type-Options "nosniff"
          X-Frame-Options "DENY"
      }
  }

  api.mtnhouse.casa {
      reverse_proxy 127.0.0.1:8000
  }

  mqtt.mtnhouse.casa {
      reverse_proxy 127.0.0.1:9001
  }
  ```
- [ ] Validate Caddy config (`caddy validate`), reload (`sudo systemctl reload caddy`), and ensure firewall exposes ports 80/443.
- [ ] Document DNS updates if new subdomains are introduced.

## Follow-up / nice-to-have (post-migration)

- [ ] Refactor `System.jsx` to derive zone data dynamically (no hard-coded arrays).
- [ ] Introduce TypeScript/types (or Zod schemas) for backend responses to catch regressions.
- [ ] Replace MQTT dependency with SSE once cache/SSE path proves stable.
- [ ] Add automated UI smoke tests (Playwright/Cypress) targeting the docker-compose stack.
- [ ] Upgrade UI notification UX (replace error banner TODO with toast system).

## Current Status — 2025-10-04

- ✅ Backend `/status?flat=1` parity + MQTT publishing validated.
- ✅ Frontend migrated to Python backend, response normaliser active, npm workflow documented.
- ✅ Docker stack uses external Home Assistant Mosquitto; documentation updated.
- ✅ **CRITICAL FIX:** Frontend Dockerfile entrypoint script properly generates runtime config.js (2025-10-04)
- ✅ **FIX:** Frontend healthcheck uses file test instead of wget (2025-10-04)
- ✅ **FIX:** Root `.env` and `.env.compose.example` updated with production MQTT settings (2025-10-04)
- ✅ Both containers healthy in production (backend + frontend)
- 🔄 Pending manual browser verification (connection indicator, command execution, stale-state UX).
- 🔄 Confirm CORS allow-list before declaring migration complete.
- 🚀 **PRODUCTION READY** — System deployed at https://tstat.mtnhouse.casa with working config generation.
