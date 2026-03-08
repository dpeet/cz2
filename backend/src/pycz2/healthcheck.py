# src/pycz2/healthcheck.py
"""Healthcheck integration for external monitoring services."""

import logging
import socket
from datetime import datetime, timezone

import httpx

from .config import settings

log = logging.getLogger(__name__)

# Module-level singleton to avoid per-call client creation overhead
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=settings.HEALTHCHECK_TIMEOUT)
    return _http_client


async def send_healthcheck_ping() -> None:
    """
    Send healthcheck ping to monitoring service (fire-and-forget).

    This function is designed to be called via asyncio.create_task() and will
    not raise exceptions. Success is logged at INFO, failures at WARNING.

    The healthcheck is only sent if HEALTHCHECK_UUID is configured.
    """
    if not settings.HEALTHCHECK_UUID:
        return

    url = f"{settings.HEALTHCHECK_BASE_URL}/{settings.HEALTHCHECK_UUID}"

    payload = {
        "hostname": socket.gethostname(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "zones": settings.CZ_ZONES,
    }

    try:
        client = _get_http_client()
        response = await client.post(url, json=payload)
        response.raise_for_status()
        log.info("Healthcheck ping sent successfully")
    except httpx.TimeoutException:
        log.warning("Healthcheck ping timed out after %ds", settings.HEALTHCHECK_TIMEOUT)
    except httpx.HTTPStatusError as e:
        log.warning("Healthcheck ping failed with status %d", e.response.status_code)
    except Exception as e:
        log.warning("Healthcheck ping failed: %s", e)
