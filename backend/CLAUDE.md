# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`cz2` is the Python backend for the Mountain House Thermostat project. It
provides a FastAPI service, CLI utilities, and MQTT integration for Carrier
ComfortZone II systems. HVAC communication is handled via RS-485 (typically
bridged over TCP) using asynchronous clients and a caching layer.

## Architecture

- **FastAPI server** (`src/pycz2/api.py`): REST endpoints for system/zone
   control, `/status?flat=1` parity responses, SSE streaming, and
   202/command-tracking semantics consumed by the frontend and MQTT clients.
- **HVAC service** (`src/pycz2/hvac_service.py`): Orchestrates cache refreshes,
   command execution, and metadata (staleness, control disable reasons).
- **MQTT publisher** (`src/pycz2/mqtt.py`): Uses `aiomqtt` with `asyncio.Lock`
   serializing all connect/disconnect/publish. Publishes status (retained) to
   `hvac/cz2/status` and audit events (non-retained) to `hvac/cz2/audit`.
- **CLI entrypoints** (`src/pycz2/cli.py`): Operational tooling for status
   checks, zone adjustments, and monitoring during troubleshooting.
- **Command reference** (`docs/API_COMMANDS.md`): Human-readable contract for
   all POST command endpoints (system, fan, zones, update).
- **Core protocol modules** (`src/pycz2/core/`): Frame encoding/decoding,
   transport abstractions, and typed models.

## Common Development Commands

```bash
cd cz2

# Install dependencies into .venv using uv
uv sync --frozen

# Run FastAPI server
uv run pycz2 api

# CLI helpers
uv run pycz2 cli status
uv run pycz2 cli set-zone 1 --heat 68 --temp
uv run pycz2 cli monitor

# Tests & quality gates
uv run pytest
uv run ruff check .
uv run pyright src/

# Container build/publish
docker build -t mountainstat-backend .
docker run --rm --env-file .env -p 8000:8000 mountainstat-backend
```

## Configuration

Environment variables (see `.env.example`) control connectivity:

```env
CZ_CONNECT=10.0.1.20:8899      # TCP bridge to HVAC (or /dev/ttyUSB0)
CZ_ZONES=4                     # Number of zones
MQTT_ENABLED=true              # Enable MQTT publisher
MQTT_HOST=host.docker.internal # External broker hostname/IP
MQTT_PORT=1883
MQTT_TOPIC_PREFIX=hvac/cz2
MQTT_PUBLISH_INTERVAL=60
ENABLE_CACHE=true              # Serve cached data when HVAC offline
ENABLE_SSE=true                 # Push updates over /events SSE stream
SSE_HEARTBEAT_INTERVAL=30
COMMAND_TIMEOUT_SECONDS=30
API_HOST=0.0.0.0
API_PORT=8000
```

## Tests

- `uv run pytest` (full suite) – includes parity checks in
   `tests/api/test_status_flat.py`.
- Targeted tests can be run via `uv run pytest tests/api/test_status_flat.py`
   when adjusting response serialization.

## Caddy/Tailscale Identity Headers

Caddy sends identity headers for Tailscale users:
- `X-Webauth-User`, `X-Webauth-Name`, `X-Webauth-Login` — Tailscale identity
- `X-Real-IP` — client IP (always present)
- Trusted IPs get `X-Real-IP` only (identity headers stripped by Caddy)
- Consumed by `_get_caller()` in `api.py` for audit logging

## Audit Logging

- `pycz2.audit` logger (propagate=False) — command audit + state change detection
- Command audit: logs caller identity, operation, and args for all POST handlers
- State detection: `UNEXPECTED` warnings in `_refresh_once` when zone state changes during background polls without a preceding command
- View: `docker compose logs cz2 | grep pycz2.audit`
- MQTT audit: both audit sites publish to `hvac/cz2/audit` via fire-and-forget `asyncio.create_task()` (avoids blocking HVAC lock or API response)
- Audit JSON format: `{"event": "command"|"unexpected_change", "timestamp": "...", ...}`

## CZ2 Hold Mode Hardware

- `temp` and `hold` are independent bits: Table 1, Row 12, Byte 9 (temp) and Byte 10 (hold)
- Perl legacy treats them as mutually exclusive — never sets both simultaneously
- CZ2 behavior with both bits set is undocumented — see `docs/todo/hold-override-bug.md`

## Known Follow-ups

- Worker remains disabled (CLI/cron style operation). Re-enabling background
   polling will require careful cache+scheduler updates.
- SSE endpoint is live and consumed by the `mountainstat/` SSE prototype;
   coordinate with `mountainstat-main` when migrating the production UI to
   /events.
- Additional integration tests for command workflows (fan, temperature) are
   planned after manual validation.
