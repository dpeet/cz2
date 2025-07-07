# pycz2 Project Overview

## Purpose
pycz2 is a Python-based toolkit for monitoring and controlling Carrier ComfortZone II HVAC systems via RS-485 serial communication. It's a complete rewrite of an original Perl implementation, providing:
- Command-line interface (CLI)
- FastAPI web server
- MQTT publisher for home automation integration
- Robust error handling and modern async I/O

## Tech Stack
- **Python 3.13+** - Main language
- **FastAPI** - Web API framework
- **Typer** - CLI framework with Rich output
- **Pydantic** - Data validation and settings management
- **Construct** - Binary protocol parsing
- **pyserial-asyncio** - Async serial communication
- **asyncio-mqtt** - MQTT integration
- **uv** - Fast Python package manager

## Project Structure
```
pycz2/
├── src/pycz2/           # Main package
│   ├── __main__.py      # Entry point
│   ├── cli.py           # CLI commands
│   ├── api.py           # FastAPI endpoints
│   ├── mqtt.py          # MQTT publisher
│   ├── config.py        # Settings management
│   └── core/            # Core functionality
│       ├── client.py    # HVAC client
│       ├── frame.py     # Binary frame parsing
│       ├── models.py    # Pydantic models
│       └── constants.py # Protocol constants
├── tests/               # Test suite
├── perl-legacy/         # Original Perl implementation
└── pyproject.toml       # Project configuration
```

## Key Features
- Asynchronous I/O for efficient communication
- Type hints throughout for better IDE support
- Comprehensive error handling
- Configuration via .env file
- Web API with automatic documentation (Swagger UI)
- MQTT integration for home automation