# src/pycz2/hvac_service.py
"""
HVAC Service Layer with CLI-style operations and smart caching.

This service replaces the persistent worker with a proven pattern:
- Connect -> Execute -> Disconnect for each operation
- Background refresh loop updates cache periodically
- All operations serialized through a single lock
"""
import asyncio
import contextlib
import logging
import time
from typing import Any, Optional, Tuple

from .cache import get_cache, CacheMeta
from .config import settings
from .core.client import get_client, get_lock
from .core.models import SystemStatus

log = logging.getLogger(__name__)


class HVACService:
    """Service for HVAC operations using CLI-style connect/execute/disconnect pattern."""

    def __init__(self):
        """Initialize the HVAC service."""
        self._op_lock = get_lock()  # Serialize all HVAC bus access
        self._refresh_task: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()
        self._last_refresh_time = 0
        self._consecutive_errors = 0
        self._max_consecutive_errors = 5

    async def start(self):
        """Start the background refresh loop."""
        if self._refresh_task is None:
            log.info("Starting HVAC service background refresh loop")
            self._refresh_task = asyncio.create_task(self._refresh_loop())

    async def stop(self):
        """Stop the background refresh loop."""
        if self._refresh_task:
            log.info("Stopping HVAC service background refresh loop")
            self._stop_event.set()
            self._refresh_task.cancel()
            with contextlib.suppress(Exception):
                await self._refresh_task
            self._refresh_task = None
            self._stop_event.clear()

    async def get_status(
        self,
        force_refresh: bool = False,
        include_raw: bool = False,
    ) -> Tuple[Optional[SystemStatus], CacheMeta]:
        """
        Get system status from cache or fresh from HVAC.

        Args:
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            Tuple of (SystemStatus or None, CacheMeta)
        """
        cache = await get_cache()

        # Always get current cache state first
        status, meta = await cache.get()

        # Return cached if fresh enough and not forced
        if not force_refresh:
            # Use configured staleness threshold
            if not meta.is_stale():
                if include_raw and (status is None or status.raw is None):  # pyright: ignore[reportUnnecessaryComparison]
                    log.debug("Cached status lacks raw blob; refreshing with raw data")
                else:
                    log.debug(
                        f"Returning cached status (age: {time.time() - meta.last_update_ts:.1f}s)"
                    )
                    return status, meta

        # Need fresh data
        log.info(
            f"Fetching fresh status (force={force_refresh}, stale={meta.is_stale()}, raw={include_raw})"
        )
        return await self._refresh_once(
            source="force" if force_refresh else "auto",
            include_raw=include_raw,
            raise_on_error=force_refresh,
        )

    async def execute_command(self, operation: str, **kwargs: Any) -> SystemStatus:
        """
        Execute a command using CLI-style pattern.

        Lock acquisition and command execution have separate timeouts so that
        a blocked lock doesn't eat into command time, and vice versa.
        """
        log.info(f"Executing command: {operation} with args: {kwargs}")

        client = get_client()
        cache = await get_cache()

        started_at = time.monotonic()
        lock_acquired_at: float | None = None
        connection_entered_at: float | None = None
        status_fetch_started_at: float | None = None

        # Step 1: Acquire lock with its own timeout
        try:
            await asyncio.wait_for(
                self._op_lock.acquire(),
                timeout=settings.LOCK_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            error_msg = (
                f"Could not acquire HVAC lock within {settings.LOCK_TIMEOUT_SECONDS}s"
            )
            log.error(error_msg)
            await cache.update(None, source="error", error=error_msg)
            raise TimeoutError(error_msg)

        lock_acquired_at = time.monotonic()
        log.info(
            "Command %s acquired HVAC lock after %.3fs",
            operation,
            lock_acquired_at - started_at,
        )

        # Step 2: Execute with command timeout (clock starts AFTER lock acquired)
        try:
            async def _execute():
                nonlocal connection_entered_at, status_fetch_started_at

                async with client.connection():
                    connection_entered_at = time.monotonic()

                    if operation == "set_system_mode":
                        mode = kwargs.get("mode")
                        all_zones = kwargs.get("all_zones", None)
                        await client.set_system_mode(
                            mode=mode, all_zones_mode=all_zones,
                        )
                    elif operation == "set_fan_mode":
                        await client.set_fan_mode(kwargs["fan_mode"])
                    elif operation == "set_zone_setpoints":
                        zones = kwargs["zones"]
                        setpoint_kwargs: dict[str, Any] = {"zones": zones}
                        for key in (
                            "heat_setpoint", "cool_setpoint",
                            "temporary_hold", "hold", "out_mode",
                        ):
                            value = kwargs.get(key)
                            if value is not None:
                                setpoint_kwargs[key] = value
                        await client.set_zone_setpoints(**setpoint_kwargs)
                    else:
                        raise ValueError(f"Unknown operation: {operation}")

                    status_fetch_started_at = time.monotonic()
                    log.debug("Fetching fresh status after command")
                    return await client.get_status_data()

            status = await asyncio.wait_for(
                _execute(),
                timeout=settings.COMMAND_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            error_msg = (
                f"HVAC command timed out after {settings.COMMAND_TIMEOUT_SECONDS}s. "
                "The HVAC controller may be unresponsive."
            )
            log.error("%s (elapsed=%.3fs)", error_msg, time.monotonic() - started_at)
            await cache.update(None, source="error", error=error_msg)
            raise TimeoutError(error_msg)
        except Exception as e:
            log.error("Command execution failed: %s (elapsed=%.3fs)", e, time.monotonic() - started_at)
            await cache.update(None, source="error", error=str(e))
            raise
        finally:
            self._op_lock.release()

        await cache.update(status, source="command")
        self._consecutive_errors = 0

        log.info(
            "Command %s completed in %.3fs",
            operation,
            time.monotonic() - started_at,
        )
        return status

    async def _refresh_once(
        self, source: str = "auto", include_raw: bool = False,
        raise_on_error: bool = False,
    ) -> Tuple[Optional[SystemStatus], CacheMeta]:
        """Perform a single refresh operation with separate lock/command timeouts."""
        client = get_client()
        cache = await get_cache()
        started_at = time.monotonic()

        # Step 1: Acquire lock with its own timeout
        try:
            await asyncio.wait_for(
                self._op_lock.acquire(),
                timeout=settings.LOCK_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            error_msg = f"Could not acquire HVAC lock within {settings.LOCK_TIMEOUT_SECONDS}s"
            log.error(error_msg)
            await cache.update(None, source="error", error=error_msg)
            if raise_on_error:
                raise TimeoutError(error_msg)
            return await cache.get()

        # Step 2: Execute refresh with command timeout (clock starts AFTER lock)
        try:
            async def _do_refresh():
                async with client.connection():
                    log.debug(f"Fetching status data from HVAC (raw={include_raw})")
                    status = await client.get_status_data(include_raw=include_raw)

                if not isinstance(status, SystemStatus):  # pyright: ignore[reportUnnecessaryIsInstance]
                    raise TypeError(f"Unexpected status type: {type(status)!r}")
                return status

            status = await asyncio.wait_for(
                _do_refresh(),
                timeout=settings.COMMAND_TIMEOUT_SECONDS,
            )

            await cache.update(status, source=source)
            self._consecutive_errors = 0
            self._last_refresh_time = time.time()
            log.info(
                "Refresh successful (source=%s, elapsed=%.3fs)",
                source, time.monotonic() - started_at,
            )

        except Exception as e:
            self._consecutive_errors += 1
            log.error(
                "Refresh failed (%s/%s): %s (elapsed=%.3fs)",
                self._consecutive_errors,
                self._max_consecutive_errors,
                e,
                time.monotonic() - started_at,
            )
            await cache.update(None, source="error", error=str(e))
            if raise_on_error:
                raise
        finally:
            self._op_lock.release()

        return await cache.get()

    async def _refresh_loop(self):
        """Background task that refreshes cache periodically."""
        interval = getattr(settings, "CACHE_REFRESH_INTERVAL", 120)

        log.info(f"Background refresh loop started (interval: {interval}s)")

        # Initial delay to let system stabilize
        await asyncio.sleep(5)

        while not self._stop_event.is_set():
            try:
                await self._refresh_once(source="auto_refresh")

                # Single sleep: use the longer of normal interval or error backoff
                if self._consecutive_errors > 0:
                    backoff = min(2 ** self._consecutive_errors, 300)
                    sleep_time = max(interval, backoff)
                    log.warning(
                        f"Backing off {sleep_time}s due to {self._consecutive_errors} errors"
                    )
                else:
                    sleep_time = interval
                await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                log.info("Refresh loop cancelled")
                break
            except Exception as e:
                log.error(f"Unexpected error in refresh loop: {e}")
                await asyncio.sleep(30)

        log.info("Background refresh loop stopped")


# Global service instance (singleton pattern like cache/sse)
_service: Optional[HVACService] = None
_service_lock = asyncio.Lock()


async def get_hvac_service() -> HVACService:
    """
    Get the global HVAC service instance (singleton).

    Returns:
        The HVAC service instance
    """
    global _service

    if _service is None:
        async with _service_lock:
            if _service is None:
                _service = HVACService()
                await _service.start()

    return _service


async def shutdown_hvac_service():
    """Shutdown the HVAC service cleanly."""
    global _service

    if _service is not None:
        await _service.stop()
        _service = None
