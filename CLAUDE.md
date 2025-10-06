# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`cz2` is the Python backend for the Mountain House Thermostat project. It
provides a FastAPI service, CLI utilities, and MQTT integration for Carrier
ComfortZone II systems. HVAC communication is handled via RS-485 (typically
bridged over TCP) using asynchronous clients and a caching layer.

## Architecture

- **FastAPI server** (`src/pycz2/api.py`): REST endpoints for system/zone
   control and the `/status?flat=1` parity response consumed by the frontend and
   MQTT subscribers.
- **HVAC service** (`src/pycz2/hvac_service.py`): Orchestrates cache refreshes,
   command execution, and metadata (staleness, control disable reasons).
- **MQTT publisher** (`src/pycz2/mqtt.py`): Uses `aiomqtt` with an async context
   manager to publish snapshots to `hvac/cz2`.
- **CLI entrypoints** (`src/pycz2/cli.py`): Operational tooling for status
   checks, zone adjustments, and monitoring during troubleshooting.
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
uv run mypy src/
uv run pyright src/
uv run pylint src/ --errors-only
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
API_HOST=0.0.0.0
API_PORT=8000
```

## Tests

- `uv run pytest` (full suite) – includes parity checks in
   `tests/api/test_status_flat.py`.
- Targeted tests can be run via `uv run pytest tests/api/test_status_flat.py`
   when adjusting response serialization.

## Known Follow-ups

- Worker remains disabled (CLI/cron style operation). Re-enabling background
   polling will require careful cache+scheduler updates.
- SSE endpoint exists but is not yet part of the production flow; integration
   will follow once MQTT usage is battle-tested.
- Additional integration tests for command workflows (fan, temperature) are
   planned after manual validation.
