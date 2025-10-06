# pycz2 - Python Carrier ComfortZone II Controller

## Overview

`pycz2` is a Python-based toolkit for monitoring and controlling a Carrier ComfortZone II HVAC system. It provides a command-line interface (CLI), a web API (using FastAPI), and an MQTT publisher to integrate your HVAC system with modern home automation platforms.

This project is a complete rewrite of the original Perl `cz2` script, addressing its limitations and adding new features in a structured, modern Python application.

## Features

- **Command-Line Interface (CLI)**: Full-featured CLI for status checks, setting temperatures, changing modes, and low-level debugging.
- **Web API**: A robust FastAPI server that exposes all control functions via simple HTTP endpoints, replacing the need for Node-RED wrappers.
- **MQTT Integration**: A built-in MQTT publisher that periodically sends system status updates, perfect for Home Assistant or other automation systems.
- **Modern and Robust**: Asynchronous I/O for efficient communication, proper error handling, and structured code.
- **Easy Configuration**: All settings are managed via a standard `.env` file.
- **Dependency Management**: Uses `uv` for fast and reliable dependency management.

## Pre-Requisites

1.  **Python 3.9+**
2.  **`uv`**: A fast Python package installer and resolver. Install it with `pip install uv`.
3.  **Hardware Connection**: An RS-485 connection to your ComfortZone II panel. This can be a local serial-to-USB adapter (e.g., `/dev/ttyUSB0`) or a remote serial-to-network adapter (e.g., a USR-W610). The required serial parameters are 9600 baud, 8 data bits, no parity, 1 stop bit (9600,8,N,1).

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd pycz2
    ```

2.  **Install dependencies with uv:**
    ```bash
    # Sync dependencies from lockfile (recommended for production)
    uv sync --frozen --no-dev

    # OR: Install in editable mode for development
    uv pip install -e .
    ```

    **Note:** This project uses `uv` for fast, reliable dependency management.
    The `uv sync` command respects the lockfile and is preferred over `pip`.
    Use `--no-dev` to skip development dependencies in production environments.

## Configuration

Configuration is handled via an `.env` file in the project root. All settings
have sensible defaults for local development; you only need to customize
connection and MQTT broker details for your specific environment.

1.  **Copy the example file:**
    ```bash
    cp .env.example .env
    ```

2.  **Edit `.env` with your settings:**

    The `.env.example` file documents all available configuration options with
    inline comments. Key settings to review:

    - **`CZ_CONNECT`**: HVAC connection string (`host:port` or `/dev/ttyUSB0`)
    - **`CZ_ZONES`**: Number of zones in your system (1-8)
    - **`CZ_ZONE_NAMES`**: Optional comma-separated zone names
    - **`MQTT_ENABLED`**: Set to `true` to enable MQTT publishing
    - **`MQTT_HOST`** / **`MQTT_PORT`**: Your MQTT broker address
    - **`CACHE_REFRESH_INTERVAL`**: Background polling interval (seconds)
    - **`ENABLE_SSE`**: Enable Server-Sent Events for real-time updates

    **MQTT Requirements:** If you enable MQTT (`MQTT_ENABLED=true`), ensure
    your broker is reachable at the specified `MQTT_HOST` and `MQTT_PORT`.
    Authentication (`MQTT_USER`, `MQTT_PASSWORD`) is optional and depends on
    your broker configuration.

    See `.env.example` for complete documentation of all available settings.

## Development Setup

### Installing Development Dependencies

To install the linting tools for development:

```bash
uv pip install -e .[dev]
```

### Linting Tools

The project uses the following linting tools:

- **Ruff**: Fast Python linter for code style and common issues
- **MyPy**: Static type checking for Python
- **Pylint**: Comprehensive Python code analysis  
- **Pyright**: Microsoft's static type checker (same engine as Pylance)

### Running Linters

Run all linters to check code quality:

```bash
# Style and basic linting
uv run ruff check .

# Type checking with MyPy
uv run mypy src/

# Comprehensive code analysis
uv run pylint src/ --errors-only

# Advanced type checking (Pylance engine)
uv run pyright src/
```

### Linting Configuration

- **MyPy**: Configured in `pyproject.toml` with `ignore_missing_imports = true`
- **Ruff**: Uses default configuration with all checks enabled
- **Pylint**: Run with `--errors-only` to focus on critical issues
- **Pyright**: Uses default strict type checking

All linting tools should pass with zero errors before submitting code.

## Usage

The application can be run as a CLI or as a web server.

### Web API & MQTT Publisher

To run the FastAPI server and the background MQTT publisher, use the `api` command:

```bash
# Using the pycz2 CLI wrapper
pycz2 api

# OR: Run directly with uvicorn via uv
uv run uvicorn pycz2.api:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://<your_ip>:8000`. Interactive documentation
(Swagger UI) is available at `http://<your_ip>:8000/docs`.

**Note:** The `uv run` command automatically manages the virtual environment and
executes commands in the correct context, eliminating the need for manual
activation.

#### API Endpoints

**Status Queries:**
-   `GET /status`: Get the current HVAC status (supports `?flat=1` for legacy format)
-   `GET /health`: Service health check

**Command API:**
-   `POST /update`: Force a refresh of the HVAC status and publish to MQTT
-   `POST /system/mode`: Set the system mode (`Heat`, `Cool`, `Auto`, `EHeat`, `Off`)
-   `POST /system/fan`: Set the system fan mode (`Auto`, `On`)
-   `POST /zones/{zone_id}/temperature`: Set a zone's temperature setpoints
-   `POST /zones/{zone_id}/hold`: Set or release hold/temporary status for a zone

📘 **[View Complete Command API Documentation](docs/API_COMMANDS.md)** for detailed
request/response schemas, validation rules, and usage examples.

Check the interactive `/docs` page (Swagger UI) for a full endpoint reference.

### Command-Line Interface (CLI)

The CLI provides the same functionality as the original Perl script.

```bash
# Get help
pycz2 cli --help

# Get system status
pycz2 cli status

# Set zone 1 heat to 68 degrees (in temporary mode)
pycz2 cli set-zone 1 --heat 68 --temp

# Set system mode to auto
pycz2 cli set-system --mode auto

# Monitor all raw bus traffic
pycz2 cli monitor
```

**Using `uv run`:** All CLI commands can also be invoked via `uv run`:

```bash
uv run pycz2 cli status
uv run pycz2 cli set-zone 1 --heat 68 --temp
```
