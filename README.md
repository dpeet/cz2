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

2.  **Create a virtual environment:**
    ```bash
    uv venv
    source .venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    uv pip install -e .
    ```
    This installs the project in editable mode.

## Configuration

Configuration is handled via an `.env` file. Copy the example file and edit it to match your setup.

1.  **Copy the example file:**
    ```bash
    cp .env.example .env
    ```

2.  **Edit `.env`:**

    ```dotenv
    # Connection string: host:port for TCP or /dev/ttyS0 for serial
    CZ_CONNECT="10.0.1.20:8899"

    # Number of zones in your system (1-8)
    CZ_ZONES=4

    # Optional: List of zone names (comma-separated)
    CZ_ZONE_NAMES="Main Room,Upstairs Bedroom,Downstairs,Unused"

    # Optional: Device ID for the script on the serial bus (must be unique)
    CZ_ID=99

    # --- MQTT Settings (Optional) ---
    MQTT_HOST="your_mqtt_broker_ip"
    MQTT_PORT=1883
    MQTT_USER=""
    MQTT_PASSWORD=""
    # Base topic for publishing status data
    MQTT_TOPIC_PREFIX="hvac/cz2"
    # How often to publish status to MQTT (in seconds)
    MQTT_PUBLISH_INTERVAL=60

    # --- API Server Settings ---
    API_HOST="0.0.0.0"
    API_PORT=8000
    ```

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
pycz2 api
```

The API will be available at `http://<your_ip>:8000`. Interactive documentation (Swagger UI) is available at `http://<your_ip>:8000/docs`.

#### API Endpoints

-   `GET /status`: Get the current HVAC status.
-   `POST /update`: Force a refresh of the HVAC status and publish to MQTT.
-   `POST /system/mode`: Set the system mode (`heat`, `cool`, `auto`, `eheat`, `off`).
-   `POST /system/fan`: Set the system fan mode (`auto`, `on`).
-   `POST /zones/{zone_id}/temperature`: Set a zone's temperature setpoints.
-   ... and more! Check the `/docs` page for a full list.

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
