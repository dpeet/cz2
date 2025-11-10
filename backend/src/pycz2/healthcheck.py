# src/pycz2/healthcheck.py
"""Healthcheck integration for external monitoring services."""

import logging
import socket
from datetime import datetime, timezone

import httpx

from .config import settings

log = logging.getLogger(__name__)


async def send_healthcheck_ping() -> None:
    """
    Send healthcheck ping to monitoring service (fire-and-forget).

    This function is designed to be called via asyncio.create_task() and will
    not raise exceptions. All errors are logged at DEBUG level to avoid log spam.

    The healthcheck is only sent if HEALTHCHECK_UUID is configured.
    """
    if not settings.HEALTHCHECK_UUID:
        return

    url = f"{settings.HEALTHCHECK_BASE_URL}/{settings.HEALTHCHECK_UUID}"

    # Build payload with basic system info
    payload = {
        "hostname": socket.gethostname(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "zones": settings.CZ_ZONES,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.HEALTHCHECK_TIMEOUT) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            log.debug("Healthcheck ping sent to %s", url)
    except httpx.TimeoutException:
        log.debug("Healthcheck ping timed out after %ds", settings.HEALTHCHECK_TIMEOUT)
    except httpx.HTTPStatusError as e:
        log.debug("Healthcheck ping failed with status %d", e.response.status_code)
    except Exception as e:
        log.debug("Healthcheck ping failed: %s", e)
