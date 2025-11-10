# Mountain House Thermostat

Dual-component HVAC control system for Carrier ComfortZone II systems:
- **backend**: Python backend (FastAPI + CLI + MQTT)
- **frontend**: React frontend (responsive thermostat UI)

The system communicates with HVAC controllers via RS-485 serial protocol,
providing local control and remote monitoring.

---

## Quick Start with Docker Compose

### Prerequisites
- Docker Engine 20.10+ and Docker Compose 2.0+
- RS-485 serial bridge accessible via TCP/IP (e.g., USR-W610 at
  `10.0.1.20:8899`)
- MQTT broker reachable from the host (Home Assistant Mosquitto or equiv.)

### 1. Setup Environment
```bash
# Copy environment template and customize
cp .env.compose.example .env

# Edit .env with your settings:
# - CZ_CONNECT: HVAC serial bridge IP:port or /dev/ttyUSB0
# - CZ_ZONES: Number of zones in your system
# - MQTT_HOST: MQTT broker hostname (e.g., host.docker.internal or mqtt)
# - MQTT_USER/MQTT_PASSWORD: Update for production (if using auth)
```

### 2. Build and Start Services
```bash
# Build images and start backend + frontend (broker assumed external)
docker compose up --build -d

# View logs
docker compose logs -f cz2
docker compose logs -f frontend
```

### 3. Access Services
- **Frontend**: http://localhost:4173 (thermostat web UI)
- **Backend API**: http://localhost:8000 (FastAPI with /docs for Swagger UI)
- **MQTT Broker**: External broker you configured (e.g., host.docker.internal)

### 4. Stop and Clean Up
```bash
# Stop services (preserves volumes)
docker compose down

# Stop and remove persistent data
docker compose down -v
```

---

## Docker Architecture

### Services

#### 1. Backend (`cz2`)
- **Image**: `mountainstat-backend:latest`
- **Purpose**: FastAPI server, CLI tools, MQTT publisher
- **Health Check**: `GET /status?flat=1` (30s interval)
- **Ports**: 8000 (API)
- **Volumes**: `cz2-cache` (SQLite cache DB)
- **Environment**: See `.env.compose.example` for full configuration

**CLI Access**:
```bash
# Check HVAC status
docker exec mountainstat-cz2 uv run pycz2 cli status

# Set zone 1 heat to 68°F (temporary)
docker exec mountainstat-cz2 uv run pycz2 cli set-zone 1 --heat 68 --temp

# Monitor raw RS-485 bus traffic
docker exec mountainstat-cz2 uv run pycz2 cli monitor
```

#### 2. Frontend
- **Image**: `mountainstat-frontend:latest`
- **Purpose**: React SPA served by Nginx with history API fallback
- **Health Check**: `GET /health` (30s interval)
- **Ports**: 4173 (HTTP, mapped from internal port 80)
- **Build Args**: `VITE_API_BASE_URL`, `VITE_API_TIMEOUT_MS`,
  `VITE_MQTT_WS_URL`

### Integrating with Existing Home Assistant Mosquitto

If you already have Mosquitto running via Home Assistant (or elsewhere),
point the stack at that broker (this is the default configuration):

1. **Configure host access**:
    - `docker-compose.yml` maps `host.docker.internal` to the host gateway:
       ```yaml
       cz2:
          extra_hosts:
             - "host.docker.internal:host-gateway"
       ```
    - Set `MQTT_HOST=host.docker.internal` (or the broker hostname/IP) in `.env`.

2. **Update environment files**:
    ```bash
    # Backend MQTT connection
    MQTT_HOST=host.docker.internal
    MQTT_PORT=1883

    # Frontend MQTT WebSocket URL
    VITE_MQTT_WS_URL=ws://localhost:9001      # Dev via port-forward
    # OR for production:
    VITE_MQTT_WS_URL=wss://mqtt.mtnhouse.casa
    ```

3. **Alternative network layouts**:
    - Join the Home Assistant Docker network via `networks: external: true`.
    - Use direct host networking (`MQTT_HOST=<LAN_IP>`).
    - For isolated testing, run a standalone Mosquitto container or
       reintroduce the legacy service from git history as needed.

---

## Production Deployment

### Host-Level Reverse Proxy (Caddy)
Docker Compose exposes internal ports only. Configure host-level Caddy for
TLS termination:

```caddyfile
# Frontend (HTTPS)
yourdomain.com {
    reverse_proxy localhost:4173
}

# Backend API (HTTPS)
api.yourdomain.com {
    reverse_proxy localhost:8000
}

# MQTT WebSocket (WSS)
mqtt.yourdomain.com {
    reverse_proxy localhost:9001
}
```

### Security Checklist
1. **Update .env secrets**:
   - Strong `MQTT_USER` and `MQTT_PASSWORD`
   - Restrict `CZ_CONNECT` to internal network IP
2. **Use external MQTT broker** (default):
   - Ensure `MQTT_HOST` in `.env` points to your broker
   - Remove any unused local Mosquitto configuration files
3. **Restrict port exposure**:
   - Remove `ports` mappings in `docker-compose.yml` (rely on Caddy proxy)
   - Or bind to `127.0.0.1:port` instead of `0.0.0.0:port`
4. **Enable TLS for MQTT**:
   - Update `VITE_MQTT_WS_URL` to `wss://mqtt.yourdomain.com`
   - Configure Mosquitto with TLS certificates (or use external broker)

---

## Development Workflow

### Local Development (without Docker)
See individual component READMEs:
- **Backend**: `backend/README.md` (uv/Python workflow)
- **Frontend**: `frontend/README.md` (npm/Vite workflow)

### Development Mode with Docker
1. **Live-reload backend code**:
   - Uncomment volume mount in `docker-compose.yml`:
     ```yaml
     volumes:
       - ./backend/src:/app/src:ro
     ```
   - Restart container: `docker compose restart cz2`

2. **Frontend development**:
   - Run frontend locally: `cd frontend && npm run dev`
   - Set `VITE_API_BASE_URL=http://localhost:8000` in `.env.local`

---

## Configuration Reference

### Environment Variables
See `.env.compose.example` for full documentation. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `CZ_CONNECT` | `10.0.1.20:8899` | HVAC serial bridge (TCP or `/dev/ttyUSB0`) |
| `CZ_ZONES` | `4` | Number of HVAC zones (1-8) |
| `MQTT_HOST` | `host.docker.internal` | MQTT broker hostname/IP |
| `MQTT_ENABLED` | `true` | Enable MQTT status publishing |
| `ENABLE_CACHE` | `true` | Enable in-memory cache for offline resilience |
| `ENABLE_SSE` | `true` | Enable Server-Sent Events for real-time updates |
| `CZ2_HOST_PORT` | `8000` | Host port for backend API |
| `FRONTEND_HOST_PORT` | `4173` | Host port for frontend |

### Backend API Endpoints
- `GET /status` - Full HVAC system status (zones, temps, modes)
- `GET /status?flat=1` - Flat status (for health checks)
- `POST /system/mode` - Set system mode (heat/cool/auto/off)
- `POST /system/fan` - Set fan mode (auto/on)
- `POST /zones/{id}/temperature` - Set zone temperature setpoints
- `POST /zones/{id}/hold` - Enable/disable zone hold mode
- `GET /events` - Server-Sent Events stream (real-time updates)

Full API documentation: http://localhost:8000/docs (Swagger UI)

---

## Troubleshooting

### Container won't start
```bash
# Check logs
docker compose logs cz2

# Verify environment variables
docker compose config

# Test HVAC connection (replace IP with your bridge)
docker exec mountainstat-cz2 uv run pycz2 cli status
```

### Frontend can't reach backend
1. Check backend health: `curl http://localhost:8000/status?flat=1`
2. Verify `VITE_API_BASE_URL` build arg in `docker-compose.yml` matches
   internal hostname (`http://cz2:8000`)
3. Rebuild frontend: `docker compose up --build frontend`

### MQTT connection fails
1. Confirm the broker is reachable from the host:
   ```bash
   mosquitto_sub -h host.docker.internal -p 1883 -t '$SYS/#' -C 1 -v
   ```
2. From inside the backend container:
   ```bash
   docker exec mountainstat-cz2 mosquitto_sub -h host.docker.internal -p 1883 -t '$SYS/#' -C 1 -v
   ```
3. Verify `MQTT_HOST` and `MQTT_PORT` values in `.env` match your broker.

### HVAC connection timeout
1. Verify serial bridge IP/port is reachable:
   ```bash
   docker exec mountainstat-cz2 nc -zv 10.0.1.20 8899
   ```
2. Check `CZ_CONNECT` in `.env` matches your bridge address
3. Test direct connection from host:
   ```bash
   cd backend && uv run pycz2 cli status
   ```

---

## Architecture Diagrams

```
┌──────────────────────────────────────────────────────────┐
│ Host System                                               │
│                                                           │
│  Browser ───▶ Frontend (Nginx) ───▶ Caddy (TLS)           │
│      ▲                        │                            │
│      │                        ▼                            │
│  External MQTT ◀────── Backend (cz2 API) ───▶ HVAC Bridge │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
mountain_house_thermostat/
├── backend/                 # Python backend (formerly cz2/)
│   ├── src/pycz2/          # Source code
│   │   ├── api.py          # FastAPI server
│   │   ├── cli.py          # CLI commands
│   │   └── core/           # HVAC protocol implementation
│   ├── Dockerfile          # Backend container image
│   ├── pyproject.toml      # Python dependencies (uv)
│   └── README.md           # Backend documentation
├── frontend/                # React frontend (formerly mountainstat/)
│   ├── src/                # React components
│   │   ├── App.jsx         # Main app container
│   │   └── System.jsx      # Thermostat UI
│   ├── Dockerfile          # Frontend container image (multi-stage)
│   ├── nginx.conf          # Nginx config (SPA fallback)
│   └── package.json        # Node dependencies (npm)
├── docs/                    # Project-wide documentation
│   ├── AGENTS.md
│   ├── HOLD_MODE_ANALYSIS.md
│   ├── FRONTEND_ERROR_REPORTING.md
│   └── Comfort_Zone_II.pdf
├── docker-compose.yml       # Orchestration config
├── .env.compose.example     # Environment template
└── README.md                # This file
```

---

## License

See `LICENSE` file in backend/ directory.

## Contributing

See `CLAUDE.md` for development guidelines and component-specific documentation
in `backend/CLAUDE.md`.
