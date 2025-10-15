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
from .core.constants import FanMode, SystemMode
from .core.models import SystemStatus

log = logging.getLogger(__name__)


class HVACService:
    """Service for HVAC operations using CLI-style connect/execute/disconnect pattern."""

    def __init__(self):
        """Initialize the HVAC service."""
        self._op_lock = get_lock()  # Serialize all HVAC bus access
        self._refresh_task: Optional[asyncio.Task] = None
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
                if include_raw and (status is None or status.raw is None):
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
        )

    async def execute_command(self, operation: str, **kwargs) -> SystemStatus:
        """
        Execute a command using CLI-style pattern.

        Args:
            operation: Command type (set_system_mode, set_fan_mode, etc.)
            **kwargs: Command-specific arguments

        Returns:
            Fresh SystemStatus after command execution
        """
        log.info(f"Executing command: {operation} with args: {kwargs}")

        client = get_client()
        cache = await get_cache()

        started_at = time.monotonic()
        lock_acquired_at: float | None = None
        connection_entered_at: float | None = None
        status_fetch_started_at: float | None = None

        try:
            # Wrap entire operation in timeout to prevent indefinite hangs
            async def _execute_with_lock():
                nonlocal lock_acquired_at, connection_entered_at, status_fetch_started_at

                log.debug(
                    "Command %s waiting for HVAC lock (timeout=%ss)",
                    operation,
                    settings.COMMAND_TIMEOUT_SECONDS,
                )
                async with self._op_lock:
                    lock_acquired_at = time.monotonic()
                    lock_wait = lock_acquired_at - started_at
                    log.info(
                        "Command %s acquired HVAC lock after %.3fs",
                        operation,
                        lock_wait,
                    )

                    # Use connection context manager for automatic cleanup
                    async with client.connection():
                        connection_entered_at = time.monotonic()
                        connection_wait = connection_entered_at - lock_acquired_at
                        log.debug(
                            "Command %s connection established after %.3fs",
                            operation,
                            connection_wait,
                        )

                        # Execute the requested operation
                        if operation == "set_system_mode":
                            mode = kwargs.get("mode")
                            all_zones = kwargs.get("all_zones", None)
                            await client.set_system_mode(
                                mode=mode,
                                all_zones_mode=all_zones,
                            )

                        elif operation == "set_fan_mode":
                            fan_mode = kwargs["fan_mode"]
                            await client.set_fan_mode(fan_mode)

                        elif operation == "set_zone_setpoints":
                            zones = kwargs["zones"]
                            setpoint_kwargs: dict[str, Any] = {"zones": zones}
                            for key in (
                                "heat_setpoint",
                                "cool_setpoint",
                                "temporary_hold",
                                "hold",
                                "out_mode",
                            ):
                                value = kwargs.get(key)
                                if value is not None:
                                    setpoint_kwargs[key] = value
                            await client.set_zone_setpoints(**setpoint_kwargs)
                        else:
                            raise ValueError(f"Unknown operation: {operation}")

                        status_fetch_started_at = time.monotonic()
                        # Always fetch fresh status after a write operation
                        log.debug("Fetching fresh status after command")
                        status = await client.get_status_data()
                        return status

            # Execute with timeout protection
            status = await asyncio.wait_for(
                _execute_with_lock(),
                timeout=settings.COMMAND_TIMEOUT_SECONDS,
            )

            finished_at = time.monotonic()
            lock_wait = (lock_acquired_at - started_at) if lock_acquired_at else None
            connection_wait = (
                (connection_entered_at - lock_acquired_at)
                if lock_acquired_at and connection_entered_at
                else None
            )
            command_exec = (
                (status_fetch_started_at - connection_entered_at)
                if connection_entered_at and status_fetch_started_at
                else None
            )
            total_elapsed = finished_at - started_at

            # Update cache with fresh data
            await cache.update(status, source="command")

            # Reset error counter on success
            self._consecutive_errors = 0

            log.info(
                "Command %s completed successfully in %.3fs (lock_wait=%s, connect=%s, command=%s)",
                operation,
                total_elapsed,
                f"{lock_wait:.3f}s" if lock_wait is not None else "n/a",
                f"{connection_wait:.3f}s" if connection_wait is not None else "n/a",
                f"{command_exec:.3f}s" if command_exec is not None else "n/a",
            )
            return status

        except asyncio.TimeoutError:
            finished_at = time.monotonic()
            lock_wait = (lock_acquired_at - started_at) if lock_acquired_at else None
            waited_for_lock = lock_acquired_at is None
            error_msg = (
                f"HVAC operation timed out after {settings.COMMAND_TIMEOUT_SECONDS} seconds. "
                "The HVAC controller may be unresponsive or experiencing heavy bus contention."
            )
            log.error(
                "%s (waited_for_lock=%s, lock_wait=%s, elapsed=%.3fs)",
                error_msg,
                waited_for_lock,
                f"{lock_wait:.3f}s" if lock_wait is not None else "n/a",
                finished_at - started_at,
            )
            # Update cache to reflect error state
            await cache.update(None, source="error", error=error_msg)
            raise TimeoutError(error_msg)
        except Exception as e:
            finished_at = time.monotonic()
            lock_wait = (lock_acquired_at - started_at) if lock_acquired_at else None
            connection_wait = (
                (connection_entered_at - lock_acquired_at)
                if lock_acquired_at and connection_entered_at
                else None
            )
            log.error(
                "Command execution failed: %s (lock_wait=%s, connect=%s, elapsed=%.3fs)",
                e,
                f"{lock_wait:.3f}s" if lock_wait is not None else "n/a",
                f"{connection_wait:.3f}s" if connection_wait is not None else "n/a",
                finished_at - started_at,
            )
            # Update cache to reflect error state
            await cache.update(None, source="error", error=str(e))
            raise

    async def _refresh_once(
        self, source: str = "auto", include_raw: bool = False
    ) -> Tuple[Optional[SystemStatus], CacheMeta]:
        """
        Perform a single refresh operation.

        Args:
            source: Source identifier for cache metadata

        Returns:
            Tuple of (SystemStatus or None, CacheMeta)
        """
        client = get_client()
        cache = await get_cache()
        started_at = time.monotonic()
        lock_acquired_at: float | None = None
        connection_entered_at: float | None = None

        try:
            async with self._op_lock:
                lock_acquired_at = time.monotonic()
                log.debug(
                    "Refresh %s acquired HVAC lock after %.3fs",
                    source,
                    lock_acquired_at - started_at,
                )
                # CLI-style: connect, fetch, disconnect
                async with client.connection():
                    connection_entered_at = time.monotonic()
                    log.debug(
                        f"Fetching status data from HVAC (raw={include_raw})"
                    )
                    status = await client.get_status_data(include_raw=include_raw)

                if not isinstance(status, SystemStatus):
                    raise TypeError(
                        f"Unexpected status type: {type(status)!r}"
                    )

            # Update cache with fresh data
            await cache.update(status, source=source)

            # Reset error counter on success
            self._consecutive_errors = 0
            self._last_refresh_time = time.time()

            finished_at = time.monotonic()
            log.info(
                "Refresh successful (source=%s, lock_wait=%s, connect=%s, elapsed=%.3fs)",
                source,
                f"{(lock_acquired_at - started_at):.3f}s"
                if lock_acquired_at is not None
                else "n/a",
                f"{(connection_entered_at - lock_acquired_at):.3f}s"
                if lock_acquired_at is not None and connection_entered_at is not None
                else "n/a",
                finished_at - started_at,
            )

        except Exception as e:
            # Track consecutive errors
            self._consecutive_errors += 1
            log.error(
                "Refresh failed (%s/%s): %s (lock_wait=%s, elapsed=%.3fs)",
                self._consecutive_errors,
                self._max_consecutive_errors,
                e,
                f"{(lock_acquired_at - started_at):.3f}s"
                if lock_acquired_at is not None
                else "n/a",
                time.monotonic() - started_at,
            )

            # Update cache to reflect error state
            await cache.update(None, source="error", error=str(e))

        # Return current cache state
        return await cache.get()

    async def _refresh_loop(self):
        """Background task that refreshes cache periodically."""
        # Use configured interval or default to 120 seconds (conservative for bus contention)
        interval = getattr(settings, "CACHE_REFRESH_INTERVAL", 120)

        log.info(f"Background refresh loop started (interval: {interval}s)")

        # Initial delay to let system stabilize
        await asyncio.sleep(5)

        while not self._stop_event.is_set():
            try:
                # Perform refresh
                await self._refresh_once(source="auto_refresh")

                # Wait for next interval
                await asyncio.sleep(interval)

                # Exponential backoff on repeated errors
                if self._consecutive_errors > 0:
                    backoff = min(2 ** self._consecutive_errors, 300)  # Max 5 minutes
                    log.warning(f"Backing off {backoff}s due to {self._consecutive_errors} errors")
                    await asyncio.sleep(backoff)

            except asyncio.CancelledError:
                log.info("Refresh loop cancelled")
                break
            except Exception as e:
                log.error(f"Unexpected error in refresh loop: {e}")
                await asyncio.sleep(30)  # Brief pause before retry

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
