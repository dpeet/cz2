# ==============================================================================
# Mountain House Thermostat - Backend (cz2) Dockerfile
# ==============================================================================
# Production-ready Python FastAPI service for Carrier ComfortZone II control
# Built with uv for fast, reproducible Python environment management
# ==============================================================================

FROM python:3.13-slim AS base

# Install uv for Python package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Copy dependency metadata and source (Hatch requires src/ to exist during sync)
COPY pyproject.toml uv.lock README.md ./
COPY src/ src/

# Install production dependencies using uv
# --frozen: Use exact versions from lockfile (reproducible builds)
# --no-dev: Skip development dependencies
RUN uv sync --frozen --no-dev

# Copy additional documentation files (optional)
# Note: Using wildcard to make these optional
COPY LICENSE* CLAUDE.md* ./

# Copy environment template for reference (override with volume/env vars)
COPY .env.example .env.example

# Create cache directory with proper permissions
RUN mkdir -p /home/appuser/.cache/pycz2 /home/appuser/.cache/uv

# Change ownership to non-root user
RUN chown -R appuser:appuser /app /home/appuser/.cache

# Switch to non-root user
USER appuser

# Expose API server port
EXPOSE 8000

# Default: Run FastAPI server
# Override for CLI mode: docker run <image> uv run pycz2 cli status
# Override for MQTT mode: docker run <image> uv run pycz2 mqtt
CMD ["uv", "run", "uvicorn", "pycz2.api:app", "--host", "0.0.0.0", \
     "--port", "8000"]

# ==============================================================================
# CLI Usage Examples:
# - Status check: docker exec <container> uv run pycz2 cli status
# - Set zone temp: docker exec <container> uv run pycz2 cli set-zone 1 \
#                  --heat 68 --temp
# - Monitor bus:  docker exec <container> uv run pycz2 cli monitor
# ==============================================================================
