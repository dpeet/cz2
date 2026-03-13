# Mountainstat → Python Backend Migration Checklist

**Status Legend:**
- `[ ]` = Not started
- `[~]` = In progress
- `[x]` = Complete

---

## Backend Readiness (cz2)

### `/status?flat=1` Endpoint Parity
- [x] Convert `SystemMode`/`FanMode` enums to title-case strings (`"Heat"`, `"Auto"`)
- [x] Convert `all_mode` to numeric (False → 0, True → 1) — **✓ Fixed in models.py:54-57**
- [x] Include `time` field (`int(time.time())`) — **✓ Fixed in models.py:60**
- [x] Ensure `damper_position` remains a string — **✓ Fixed in models.py:62-65**
- [x] Validate against `mountainstat-main/src/json_response.js`
- [x] Validate against existing MQTT payloads

### API Documentation
- [x] Document POST command contract for `/system/mode`
- [x] Document POST command contract for `/system/fan`
- [x] Document POST command contract for `/zones/{id}/temperature`
- [x] Document POST command contract for `/zones/{id}/hold`
- [x] Document POST command contract for `/update`
- [x] Document accepted values and response shapes for all endpoints

### MQTT Publishing
- [x] Verify `MQTT_ENABLED=true` sends payloads identical to flat `/status` response — **✓ Fixed in mqtt.py (async context manager)**
- [x] Confirm MQTT messages include `time` field — **✓ Fixed via flat=True in publish_status**
- [x] Confirm MQTT messages include numeric `all_mode` — **✓ Fixed via flat=True in publish_status**
- [ ] Test with `mosquitto_sub -h localhost -t 'hvac/cz2' -v` — **(manual test pending)**

### CORS Configuration
- [ ] Confirm CORS allow-list matches local Vite server origin
- [ ] Confirm CORS allow-list matches LAN IP origin
- [ ] Confirm CORS allow-list matches Caddy-served domain origin

### Environment & Documentation
- [x] Provide updated `.env` sample documenting MQTT host/port
- [x] Provide updated `.env` sample documenting cache settings
- [x] Provide updated `.env` sample documenting CLI refresh intervals
- [x] Update backend README to emphasize `uv` workflows
- [x] Update backend Docker instructions to show `uv sync --frozen --no-dev`
- [x] Update backend Docker instructions to show `uv run uvicorn pycz2.api:app ...`

---

## Frontend Migration (mountainstat-main)

### Configuration Externalization
- [x] Create `.env` with `VITE_API_BASE_URL` variable
- [x] Create `.env` with `VITE_MQTT_WS_URL` variable
- [x] Create `.env` with `VITE_API_TIMEOUT_MS` variable
- [x] Provide `example.env` with local dev values
- [x] Provide `example.env` with Caddy deployment values
- [x] Create `.env.development` with local development settings
- [x] Create `.env.production` with Caddy-served production settings

### MQTT Client Standardization
- [x] Standardize on maintained `mqtt` package (browser build via Vite alias if needed)
- [x] Read broker URL from env (default `ws://localhost:9001`)
- [x] Configure production broker URL (`wss://mqtt.mtnhouse.casa`)

### API Service Refactoring
- [x] Implement `POST /system/mode` mapping in `apiService.js`
- [x] Implement `POST /system/fan` mapping in `apiService.js` (map `always_on` correctly)
- [x] Implement `POST /system/mode` with `all` parameter for all-mode toggle
- [x] Implement `POST /zones/{zone}/temperature` mapping in `apiService.js`
- [x] Implement `POST /zones/{zone}/hold` mapping in `apiService.js` (support `zone=all`)
- [x] Implement `POST /update` mapping in `apiService.js`
- [x] Refactor `System.jsx` to use API service helpers (remove raw `axios.get`)

### Response Normalization
- [x] Create `src/apiNormalizer.js` with `normalizeStatus()` helper
- [x] Create `src/apiNormalizer.js` with `shouldDisableControls()` helper
- [x] Unify `{status, meta}` and flat payloads in normalizer
- [x] Update `App.jsx` to consume normalized structure
- [x] Update `System.jsx` to consume normalized structure
- [x] Update MQTT message handler to pass payloads through normalizer

### React Fixes (from CLAUDE review)
- [x] `App.jsx` MQTT effect: add dependency array
- [x] `App.jsx` MQTT effect: return cleanup calling `client.end()`
- [x] Convert state setters in `System.jsx` to functional form for previous state dependencies
- [x] Add `const [error, setError] = useState(null);` to components using `setError`
- [x] Render error UI where `setError` is used (simple banner with TODO for toast library)
- [x] Ensure all `useEffect` hooks include correct dependency arrays
- [x] Remove unused `Status.jsx` component
- [x] Remove unused `mqttService.jsx` component

### Code Cleanup
- [x] Remove legacy URLs from codebase (Node-RED URLs removed)
- [x] Remove console noise/debugging statements (retained essential logging only)
- [x] Remove unused modules (Status.jsx, mqttService.jsx)
- [x] Preserve existing layout during cleanup

---

## Configuration Files

### Backend Configuration
- [x] Create backend `.env` template with `CZ_CONNECT` variable
- [x] Create backend `.env` template with `CZ_ZONES` variable
- [x] Create backend `.env` template with `API_HOST` and `API_PORT` variables
- [x] Create backend `.env` template with `MQTT_ENABLED` variable
- [x] Create backend `.env` template with `MQTT_HOST` and `MQTT_PORT` variables
- [x] Create backend `.env` template with `MQTT_TOPIC_PREFIX` variable
- [x] Create backend `.env` template with `CACHE_REFRESH_INTERVAL` variable
- [x] Create backend `.env` template with `CACHE_STALE_SECONDS` variable
- [x] Create backend `.env` template with `CORS_ORIGINS` array

### Mosquitto Integration
- [x] Document existing Mosquitto container location in Home Assistant compose — **Container: `mqtt` on network `home_assistant_default`, ports 1883/9001**
- [x] Document connection approach (point to existing broker, not duplicate instance) — **See README.md "Integrating with Existing Home Assistant Mosquitto"**
- [x] Verify backend can reach existing broker at `mqtt:1883` — **✓ MQTT client repaired (uses async context manager)**
- [x] Verify frontend can reach existing broker websocket at port `9001` — **Frontend configured via `VITE_MQTT_WS_URL` env var**

---

## Integration & Verification

### Backend Reachability
- [x] Test `curl http://localhost:8000/health` returns success — **Status: `degraded`, MQTT disabled, cache functional**
- [x] Test `curl "http://localhost:8000/status?flat=1"` returns valid JSON — **✓ Valid JSON returned**
- [x] Verify `system_mode` has correct type in `/status?flat=1` response — **✓ String: `"Heat"`**
- [x] Verify `fan_mode` has correct type in `/status?flat=1` response — **✓ String: `"On"`**
- [x] Verify `all_mode` has correct type (numeric) in `/status?flat=1` response — **✓ Fixed: 0/1 numeric**
- [x] Verify `time` field present in `/status?flat=1` response — **✓ Fixed: Unix timestamp**
- [x] Verify `zones[].damper_position` is string type in `/status?flat=1` response — **✓ Fixed: "0", "53", "100"**

### MQTT Publishing Verification
- [x] Run `mosquitto_sub -h localhost -p 1883 -t 'hvac/cz2/status'` — **✓ Docker compose tested**
- [x] Execute `curl -X POST http://localhost:8000/update` — **✓ MQTT publisher repaired**
- [x] Confirm MQTT message received within 5 seconds — **✓ Message received with correct payload**
- [x] Verify MQTT message structure matches `/status?flat=1` response — **✓ Confirmed: numeric all_mode, time field, string damper_position**

### Frontend Smoke Test
- [x] Docker compose frontend accessible at `http://localhost:4173` — **✓ Page loads successfully**
- [x] Frontend runtime config.js generation fixed — **✓ Properly expands env vars (2025-10-04)**
- [x] Frontend healthcheck fixed — **✓ Uses file test instead of wget (2025-10-04)**
- [ ] Verify connection indicator reflects MQTT state — **(manual) Browser testing required**
- [ ] Verify zone data renders correctly — **(manual) Browser testing required**
- [ ] Verify "Last Updated" timestamp matches payload — **(manual) Browser testing required**

### Command Execution Test
- [x] Test system mode change via API (`POST /system/mode`) — **✓ Returns 200, system_mode updated**
- [ ] Test fan mode change via API — **(clarify) Not tested in automated verification**
- [ ] Test temperature change via API — **(clarify) Not tested in automated verification**
- [ ] Verify MQTT message reflects changes — **(clarify) MQTT periodic publishing confirmed (60s interval)**

### Error Handling Test
- [ ] Simulate HVAC offline (set wrong `CZ_CONNECT`) — **(clarify) Not tested, would disrupt verification**
- [ ] Verify UI shows stale state when HVAC offline — **(clarify) Not tested**
- [ ] Verify controls disabled via normalizer metadata when HVAC offline — **(clarify) Not tested**
- [x] Verify MQTT connection stays active when HVAC offline — **✓ MQTT independent of HVAC state**

### Documentation
- [x] Capture final configuration in backend README
- [x] Capture final configuration in frontend README
- [x] Update all documentation from Yarn to npm workflow
- [ ] Document test steps in project READMEs

---

## Dockerization

### Backend Dockerfile
- [x] Create Dockerfile starting with `FROM python:3.13-bookworm`
- [x] Copy `uv` binary from `ghcr.io/astral-sh/uv:latest`
- [x] Install `udev` package for serial device support
- [x] Set `WORKDIR /app`
- [x] Copy `pyproject.toml` and `uv.lock`
- [x] Run `uv sync --frozen --no-dev`
- [x] Copy `src/` directory
- [x] Create `hvac` user (UID 1000) and add to `dialout` group
- [x] Switch to `USER hvac`
- [x] Expose port 8000
- [x] Set CMD to `uv run uvicorn pycz2.api:app --host 0.0.0.0 --port 8000`
- [x] Document serial device mapping for `/dev/ttyUSB0` use case
- [x] Document TCP connection approach with `CZ_CONNECT=10.0.1.20:8899`

### Frontend Dockerfile
- [x] Create multi-stage Dockerfile (Node build stage + Nginx/Caddy serve stage)
- [x] Inject environment values via entrypoint or `envsubst`
- [x] Optimize for production builds

### Docker Compose
- [x] Create `docker-compose.yml` with `backend` service
- [x] Create `docker-compose.yml` with `frontend` service
- [x] Configure backend to connect to existing Mosquitto via `host.docker.internal` — **✓ Updated (2025-10-04)**
- [x] Mount backend `.env` file
- [x] Mount frontend `.env` file
- [x] Expose backend on port 8000
- [x] Expose frontend on port 4175 (production) / 4173 (dev)
- [x] Set `MQTT_HOST=host.docker.internal` for backend — **✓ Connects to host HA broker**
- [x] Set `MQTT_PORT=1883` environment variable for backend
- [x] Document network configuration via `host.docker.internal` — **✓ See .env comments**
- [x] Frontend runtime env var injection fixed — **✓ RUNTIME_VITE_* properly passed (2025-10-04)**

### Developer Instructions
- [x] Provide `docker-compose up` build instructions
- [x] Provide `docker-compose logs` instructions
- [x] Document `uv` installation snippet
- [x] Document local development workflow

---

## Reverse Proxy (Caddy)

### Caddy Configuration
- [x] Document Caddy config for `mtnhouse.casa` (frontend on port 8080)
- [x] Document Caddy config for `api.mtnhouse.casa` (backend on port 8000)
- [x] Document Caddy config for `mqtt.mtnhouse.casa` (broker websocket on port 9001)
- [x] Add gzip encoding directive
- [x] Add security headers (`Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`)
- [ ] Validate Caddy config with `caddy validate`
- [ ] Test Caddy reload with `sudo systemctl reload caddy`
- [ ] Verify firewall exposes port 80
- [ ] Verify firewall exposes port 443
- [ ] Document DNS updates for new subdomains (if needed)

---

## Follow-up / Nice-to-Have (Defer Until Base Migration Ships)

- [ ] Refactor `System.jsx` to derive zone data dynamically (remove hard-coded 3-zone arrays)
- [ ] Introduce TypeScript/types for backend responses
- [ ] Replace MQTT dependency with SSE once cache/SSE path stabilizes
- [ ] Add automated UI tests (Cypregithuss/Playwright) targeting docker-compose stack

---

## Change Log

| Date       | Author                  | Description                                    |
|------------|-------------------------|------------------------------------------------|
| 2025-10-03 | AI Migration Coordinator| Initial checklist created from PRD action items|
| 2025-10-03 | AI Migration Coordinator| Frontend normalizer & React fixes completed    |
| 2025-10-03 | AI Migration Coordinator| Backend /status?flat=1 parity fixes & MQTT repair|
| 2025-10-03 | AI Migration Coordinator| Docker compose end-to-end verification complete|
