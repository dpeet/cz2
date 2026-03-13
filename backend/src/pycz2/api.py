# src/pycz2/api.py
import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from .cache import get_cache
from .config import settings
from .core.client import ComfortZoneIIClient, get_client, get_lock
from .core.models import (
    BatchZoneTemperatureArgs,
    SystemFanArgs,
    SystemModeArgs,
    SystemStatus,
    ZoneHoldArgs,
    ZoneTemperatureArgs,
)
from .mqtt import get_mqtt_client
from .sse import get_sse_manager, create_sse_response
from .hvac_service import get_hvac_service, shutdown_hvac_service

log = logging.getLogger(__name__)
audit = logging.getLogger("pycz2.audit")

# Global state to hold the background task
background_tasks = set()


def _is_truthy(value: str | None) -> bool:
    return value is not None and value.lower() in {"1", "true", "yes", "on"}


def _get_caller(request: Request) -> str:
    """Extract caller identity from Caddy/Tailscale headers."""
    user = request.headers.get("x-webauth-user")
    name = request.headers.get("x-webauth-name")
    ip = request.headers.get("x-real-ip", request.client.host if request.client else "unknown")
    if user:
        return f"{name or user} ({ip})"
    return f"anonymous ({ip})"


def _status_payload(
    status: SystemStatus | None, include_raw: bool = False, flat: bool = False
) -> dict[str, Any]:
    """Convert SystemStatus to dictionary payload."""
    return status.to_dict(include_raw=include_raw, flat=flat) if status else {}


async def _execute_and_respond(
    operation: str,
    message: str,
    request: Request,
    **kwargs: Any,
) -> dict[str, Any]:
    """Shared helper for POST command endpoints."""
    caller = _get_caller(request)
    service = await get_hvac_service()
    await service.execute_command(operation, **kwargs)
    status_obj, meta = await service.get_status(force_refresh=False)
    audit.info("command=%s caller=%s args=%s", operation, caller, kwargs)
    if settings.MQTT_ENABLED:
        asyncio.create_task(get_mqtt_client().publish_audit({
            "event": "command",
            "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
            "caller": caller,
            "command": operation,
            "args": kwargs,
        }))

    return {
        "status": _status_payload(status_obj),
        "meta": meta.to_dict(),
        "message": message,
    }


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    log.info("Starting pycz2 API server...")

    if settings.ENABLE_CACHE:
        await get_cache()
        log.info("Cache initialized")

    log.info("Starting HVAC service")
    await get_hvac_service()

    if settings.ENABLE_SSE:
        await get_sse_manager()
        log.info("SSE manager started")

    if settings.MQTT_ENABLED:
        mqtt_client = get_mqtt_client()
        await mqtt_client.connect()

        async def mqtt_publisher_task() -> None:
            """Publish to MQTT whenever the cache updates."""
            cache = await get_cache()
            queue = await cache.subscribe()
            try:
                while True:
                    update = await queue.get()
                    if update is None:
                        break
                    try:
                        status, meta = await cache.get()
                        if status and meta.source != "error":
                            await mqtt_client.publish_status(status)
                    except Exception:
                        log.exception("MQTT publish failed")
            except asyncio.CancelledError:
                pass
            finally:
                await cache.unsubscribe(queue)

        task = asyncio.create_task(mqtt_publisher_task())
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)

    yield
    # Shutdown
    log.info("Shutting down pycz2 API server...")

    await shutdown_hvac_service()
    log.info("HVAC service stopped")

    if settings.ENABLE_SSE:
        sse_manager = await get_sse_manager()
        await sse_manager.stop()
        log.info("SSE manager stopped")

    for task in background_tasks:
        task.cancel()
    if background_tasks:
        await asyncio.gather(*background_tasks, return_exceptions=True)

    if settings.MQTT_ENABLED:
        mqtt_client = get_mqtt_client()
        await mqtt_client.disconnect()
    log.info("Shutdown complete.")


app = FastAPI(
    title="pycz2 API",
    description="An API for controlling Carrier ComfortZone II HVAC systems.",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://10.0.1.15:5173",
        "http://100.68.198.76:5173",
        "http://100.68.198.76:5174",
        "https://mtnhouse.casa",
        "https://tstat.mtnhouse.casa",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/status")
async def get_current_status(
    request: Request,
    client: ComfortZoneIIClient = Depends(get_client),
    lock: asyncio.Lock = Depends(get_lock),
) -> dict[str, Any]:
    """
    Get the current system status.

    Query parameters:
    - flat=1: Return legacy flat response format (for backwards compatibility)
    - force=true: Force refresh from HVAC (bypass cache)
    """
    use_flat_format = request.query_params.get("flat") == "1"
    force_refresh = request.query_params.get("force") == "true"
    raw_requested = _is_truthy(request.query_params.get("raw"))

    if settings.ENABLE_CACHE:
        service = await get_hvac_service()
        status, meta = await service.get_status(
            force_refresh=force_refresh, include_raw=raw_requested
        )

        if use_flat_format:
            return _status_payload(status, include_raw=raw_requested, flat=True)
        else:
            return {
                "status": _status_payload(status, include_raw=raw_requested),
                "meta": meta.to_dict(),
            }
    else:
        # Legacy behavior: direct query
        async with lock, client.connection():
            try:
                status = await client.get_status_data(include_raw=raw_requested)

                if use_flat_format:
                    return _status_payload(status, include_raw=raw_requested, flat=True)
                else:
                    return {
                        "status": _status_payload(status, include_raw=raw_requested),
                        "meta": {
                            "connected": True,
                            "is_stale": False,
                            "source": "direct",
                        },
                    }
            except (TimeoutError, ConnectionAbortedError) as e:
                log.error(f"Failed to get status: {e}")
                raise HTTPException(
                    status_code=504,
                    detail="Could not communicate with HVAC controller.",
                ) from e


@app.post("/update")
async def force_update_and_publish() -> dict[str, Any]:
    """Force a status refresh from the HVAC system and publish it to MQTT."""
    try:
        service = await get_hvac_service()
        status, meta = await service.get_status(force_refresh=True)

        return {
            "status": _status_payload(status),
            "meta": meta.to_dict(),
            "message": "Status refreshed successfully",
        }
    except Exception as e:
        log.error(f"Failed to update status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/system/mode")
async def set_system_mode(
    args: SystemModeArgs,
    request: Request,
) -> dict[str, Any]:
    """Set the main system mode (heat, cool, auto, etc.)."""
    try:
        return await _execute_and_respond(
            "set_system_mode",
            f"System mode set to {args.mode}",
            request,
            mode=args.mode,
            all_zones=args.all,
        )
    except Exception as e:
        log.error(f"Failed to set system mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/system/fan")
async def set_system_fan(
    args: SystemFanArgs,
    request: Request,
) -> dict[str, Any]:
    """Set the system fan mode (auto, on)."""
    try:
        return await _execute_and_respond(
            "set_fan_mode",
            f"Fan mode set to {args.fan}",
            request,
            fan_mode=args.fan,
        )
    except Exception as e:
        log.error(f"Failed to set fan mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/zones/batch/temperature")
async def set_batch_zone_temperature(
    args: BatchZoneTemperatureArgs,
    request: Request,
) -> dict[str, Any]:
    """
    Set the heating and/or cooling setpoints for multiple zones at once.
    You must also set `hold` or `temp` to true for the change to stick.
    """
    for zone_id in args.zones:
        if not 1 <= zone_id <= settings.CZ_ZONES:
            raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found.")

    zones = list(set(args.zones))

    # Validate setpoint relationship against current zone setpoints
    service = await get_hvac_service()
    current_status, _ = await service.get_status(force_refresh=False)

    if current_status and current_status.zones:
        for zone_id in zones:
            zone = current_status.zones[zone_id - 1]

            if args.heat is not None and args.cool is None:
                if args.heat >= zone.cool_setpoint - 1:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Heat setpoint ({args.heat}°F) must be at least 2°F below "
                               f"zone {zone_id}'s cool setpoint ({zone.cool_setpoint}°F). "
                               f"Current gap would be: {zone.cool_setpoint - args.heat}°F."
                    )

            if args.cool is not None and args.heat is None:
                if args.cool <= zone.heat_setpoint + 1:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Cool setpoint ({args.cool}°F) must be at least 2°F above "
                               f"zone {zone_id}'s heat setpoint ({zone.heat_setpoint}°F). "
                               f"Current gap would be: {args.cool - zone.heat_setpoint}°F."
                    )

    try:
        zone_list = ", ".join(map(str, sorted(zones)))
        return await _execute_and_respond(
            "set_zone_setpoints",
            f"Zones {zone_list} temperature updated",
            request,
            zones=zones,
            heat_setpoint=args.heat,
            cool_setpoint=args.cool,
            temporary_hold=args.temp,
            hold=args.hold,
            out_mode=args.out,
        )
    except Exception as e:
        log.error(f"Failed to set batch zone temperature: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/zones/{zone_id}/temperature")
async def set_zone_temperature(
    zone_id: int,
    args: ZoneTemperatureArgs,
    request: Request,
) -> dict[str, Any]:
    """
    Set the heating and/or cooling setpoints for a specific zone.
    You must also set `hold` or `temp` to true for the change to stick.
    """
    if not 1 <= zone_id <= settings.CZ_ZONES:
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found.")

    # Validate setpoint relationship against current zone setpoints
    service = await get_hvac_service()
    current_status, _ = await service.get_status(force_refresh=False)

    if current_status and current_status.zones:
        zone = current_status.zones[zone_id - 1]

        if args.heat is not None and args.cool is None:
            if args.heat >= zone.cool_setpoint - 1:
                raise HTTPException(
                    status_code=422,
                    detail=f"Heat setpoint ({args.heat}°F) must be at least 2°F below "
                           f"current cool setpoint ({zone.cool_setpoint}°F). "
                           f"Current gap would be: {zone.cool_setpoint - args.heat}°F."
                )

        if args.cool is not None and args.heat is None:
            if args.cool <= zone.heat_setpoint + 1:
                raise HTTPException(
                    status_code=422,
                    detail=f"Cool setpoint ({args.cool}°F) must be at least 2°F above "
                           f"current heat setpoint ({zone.heat_setpoint}°F). "
                           f"Current gap would be: {args.cool - zone.heat_setpoint}°F."
                )

    try:
        return await _execute_and_respond(
            "set_zone_setpoints",
            f"Zone {zone_id} temperature updated",
            request,
            zones=[zone_id],
            heat_setpoint=args.heat,
            cool_setpoint=args.cool,
            temporary_hold=args.temp,
            hold=args.hold,
            out_mode=args.out,
        )
    except Exception as e:
        log.error(f"Failed to set zone temperature: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/zones/{zone_id}/hold")
async def set_zone_hold(
    zone_id: int,
    args: ZoneHoldArgs,
    request: Request,
) -> dict[str, Any]:
    """Set or release the hold/temporary status for a zone."""
    if not 1 <= zone_id <= settings.CZ_ZONES:
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found.")

    try:
        return await _execute_and_respond(
            "set_zone_setpoints",
            f"Zone {zone_id} hold settings updated",
            request,
            zones=[zone_id],
            hold=args.hold,
            temporary_hold=args.temp,
        )
    except Exception as e:
        log.error(f"Failed to set zone hold: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Monitoring and admin endpoints


@app.get("/status/live")
async def get_live_status(
    client: ComfortZoneIIClient = Depends(get_client),
    lock: asyncio.Lock = Depends(get_lock),
) -> dict[str, Any]:
    """Get live status directly from HVAC (bypasses cache)."""
    try:
        async def _fetch():
            async with lock, client.connection():
                return await client.get_status_data()

        status = await asyncio.wait_for(
            _fetch(),
            timeout=settings.LOCK_TIMEOUT_SECONDS + settings.COMMAND_TIMEOUT_SECONDS,
        )

        if settings.ENABLE_CACHE:
            cache = await get_cache()
            await cache.update(status, source="live_query")

        return {
            "status": _status_payload(status),
            "source": "live",
            "timestamp": time.time(),
        }
    except (TimeoutError, ConnectionAbortedError) as e:
        log.error(f"Failed to get live status: {e}")
        raise HTTPException(
            status_code=504, detail="Could not communicate with HVAC controller."
        ) from e
    except Exception as e:
        log.error(f"Unexpected error getting live status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cache/stats")
async def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics for monitoring."""
    if not settings.ENABLE_CACHE:
        raise HTTPException(status_code=404, detail="Cache is not enabled")

    cache = await get_cache()
    stats = await cache.get_stats()
    return stats


@app.post("/cache/clear")
async def clear_cache() -> dict[str, Any]:
    """Clear the cache (admin endpoint)."""
    if not settings.ENABLE_CACHE:
        raise HTTPException(status_code=404, detail="Cache is not enabled")

    cache = await get_cache()
    await cache.clear()
    return {"message": "Cache cleared successfully"}


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint for monitoring and load balancers."""
    health_status: dict[str, Any] = {
        "status": "healthy",
        "timestamp": time.time(),
        "features": {
            "cache_enabled": settings.ENABLE_CACHE,
            "mqtt_enabled": settings.MQTT_ENABLED,
            "sse_enabled": settings.ENABLE_SSE,
        },
    }

    if settings.ENABLE_CACHE:
        cache = await get_cache()
        cache_stats = await cache.get_stats()
        health_status["cache"] = {
            "connected": cache_stats["connected"],
            "has_data": cache_stats["has_data"],
            "is_stale": cache_stats["is_stale"],
            "age_seconds": cache_stats.get("age_seconds"),
        }

        if cache_stats["is_stale"] or not cache_stats["connected"]:
            health_status["status"] = "degraded"

    health_status["background_tasks"] = {
        "active": len(background_tasks),
        "running": all(not task.done() for task in background_tasks),
    }

    if not health_status["background_tasks"]["running"]:
        health_status["status"] = "unhealthy"

    return health_status


@app.get("/events")
async def events(request: Request):
    """Server-Sent Events endpoint for real-time updates."""
    if not settings.ENABLE_SSE:
        raise HTTPException(status_code=404, detail="SSE is not enabled")

    try:
        return await create_sse_response(request)
    except ValueError as e:
        raise HTTPException(status_code=429, detail=str(e))


@app.get("/sse/stats")
async def get_sse_stats() -> dict[str, Any]:
    """Get SSE manager statistics."""
    if not settings.ENABLE_SSE:
        raise HTTPException(status_code=404, detail="SSE is not enabled")

    sse_manager = await get_sse_manager()
    return sse_manager.get_stats()
