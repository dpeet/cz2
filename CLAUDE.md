# Mountain House Thermostat - Development Guide

This file provides guidance to Claude Code (claude.ai/code) when working with this monorepo.

## Project Overview

Mountain House Thermostat is a dual-component HVAC control system for Carrier ComfortZone II:
- **backend/**: Python backend (FastAPI + CLI + MQTT)
- **frontend/**: React frontend (responsive thermostat UI)

The system communicates with HVAC controllers via RS-485 serial protocol, providing local control and remote monitoring.

---

## Quick Development Commands

### Backend (Python/FastAPI)
```bash
cd backend

# Manage environment (uv creates .venv automatically)
uv sync --frozen

# Run API server (FastAPI)
uv run pycz2 api

# CLI commands
uv run pycz2 cli status
uv run pycz2 cli set-zone 1 --heat 68 --temp
uv run pycz2 cli set-system --mode auto
uv run pycz2 cli monitor

# Tests & tooling
uv run pytest
uv run ruff check .
uv run mypy src/
uv run pyright src/
uv run pylint src/ --errors-only
```

### Frontend (React/Vite)
```bash
cd frontend

# Install dependencies
npm install

# Development server (network accessible)
npm run dev -- --host

# Production build & preview
npm run build
npm run preview

# Tests
npm test              # unit/integration
npm run test:ui       # Vitest UI runner
```

---

## Configuration

### Backend (.env file in backend/)
```env
# Connection: host:port for TCP or /dev/ttyUSB0 for serial
CZ_CONNECT="10.0.1.20:8899"
CZ_ZONES=4
CZ_ZONE_NAMES="Main Room,Upstairs,Downstairs,Office"

# MQTT Configuration
MQTT_HOST="mqtt_broker_ip"
MQTT_PORT=1883
MQTT_TOPIC_PREFIX="hvac/cz2"
MQTT_PUBLISH_INTERVAL=60

# API Server
API_HOST="0.0.0.0"
API_PORT=8000
```

### Frontend (.env files in frontend/)
Environment configuration via Vite:
- `.env.development` - Local development (localhost:8000, ws://localhost:9001)
- `.env.production` - Production/Caddy (https://api.mtnhouse.casa, wss://mqtt.mtnhouse.casa)
- `.env.local` - Optional local overrides (not committed)

See `.env.example` for all available variables.

---

## Key API Endpoints

- `GET /status` - Current HVAC system status (zones, temps, modes)
- `POST /system/mode` - Set system mode (heat/cool/auto/off)
- `POST /system/fan` - Set fan mode (auto/on)
- `POST /zones/{id}/temperature` - Set zone temperature setpoints
- `POST /zones/{id}/hold` - Enable/disable zone hold mode
- `GET /events` - Server-Sent Events stream (real-time updates)

Full API documentation: http://localhost:8000/docs (Swagger UI)

---

## Architecture

### Backend Architecture
- **FastAPI server** (`backend/src/pycz2/api.py`): REST endpoints for system/zone
   control, `/status?flat=1` parity responses, SSE streaming, and
   202/command-tracking semantics consumed by the frontend and MQTT clients.
- **HVAC service** (`backend/src/pycz2/hvac_service.py`): Orchestrates cache refreshes,
   command execution, and metadata (staleness, control disable reasons).
- **MQTT publisher** (`backend/src/pycz2/mqtt.py`): Uses `aiomqtt` with an async context
   manager to publish snapshots to `hvac/cz2`.
- **CLI entrypoints** (`backend/src/pycz2/cli.py`): Operational tooling for status
   checks, zone adjustments, and monitoring during troubleshooting.
- **Command reference** (`backend/docs/API_COMMANDS.md`): Human-readable contract for
   all POST command endpoints (system, fan, zones, update).
- **Core protocol modules** (`backend/src/pycz2/core/`): Frame encoding/decoding,
   transport abstractions, and typed models.

---

## Testing

### Backend
```bash
cd backend
pytest tests/              # Run all tests
pytest tests/test_api.py   # Test API endpoints
pytest tests/test_cli.py   # Test CLI commands
```

### Frontend
```bash
cd frontend
npm test          # Run all tests
npm run test:ui   # Run tests with UI
```

---

## Current Focus & Follow-up

The migration to the Python backend is complete (REST parity, MQTT publishing,
response normaliser). Remaining high-level tasks:

- Document manual UI validation (connection indicator, command success)
- Finish SSE adoption after backend cache/SSE path is proven in production
- Improve zone configurability (load zone metadata dynamically)
- Replace banner TODOs with a real notification/toast system
- Add automated UI smoke tests once docker-compose stack is stable

---

## Known Issues

### Backend
- Worker remains disabled in deployment mode (CLI workflow); cache can become
  stale if HVAC bridge goes offline for extended periods.
- Health endpoint reports `degraded` when cache is stale or MQTT disabled—set
  expectations accordingly in monitoring.
- SSE endpoint exists but is not yet wired into the frontend (follow-up after
  stabilising cache + MQTT).

### Frontend
- Manual UI validation still pending for connection indicator + timestamps
- Zone list still assumes static ordering (dynamic metadata planned)
- Error UX minimal (banner with TODO for toast implementation)
- SSE migration deferred until backend SSE path stabilises

---

## Protocol Details

### HVAC Communication
- Binary frame format with CRC-16 checksums
- Master controller at address 1, panel at address 9
- Key data locations:
  - System Mode: Table 1, Row 12, Byte 4
  - Zone Setpoints: Table 1, Row 16
  - Zone Temps: Table 1, Row 24
  - System Time: Table 1, Row 18

### Temperature Encoding
- Stored as single byte: (temp_f - 34) / 2
- Valid range: 45-80°F for setpoints
