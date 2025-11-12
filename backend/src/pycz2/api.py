# src/pycz2/api.py
import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from tenacity import RetryError

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
from .mqtt import MqttClient, get_mqtt_client
from .worker import CommandType, calculate_provisional_state, get_worker
from .sse import get_sse_manager, create_sse_response
from .hvac_service import get_hvac_service, shutdown_hvac_service

log = logging.getLogger(__name__)

# Global state to hold the background task
background_tasks = set()


def _is_truthy(value: str | None) -> bool:
    return value is not None and value.lower() in {"1", "true", "yes", "on"}


def _status_payload(
    status: SystemStatus | None, include_raw: bool = False, flat: bool = False
) -> dict:
    """
    Convert SystemStatus to dictionary payload.

    Args:
        status: System status object to convert
        include_raw: Include raw HVAC data blob
        flat: Apply legacy flat format transformations (for ?flat=1)
    """
    return status.to_dict(include_raw=include_raw, flat=flat) if status else {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    log.info("Starting pycz2 API server...")

    # Initialize cache if enabled
    if settings.ENABLE_CACHE:
        await get_cache()
        log.info("Cache initialized")

    # Start HVAC service (CLI-style) if worker disabled
    if not settings.WORKER_ENABLED:
        log.info("Starting HVAC service (CLI-style mode)")
        await get_hvac_service()
        # Service starts its own background refresh loop internally

    # Start worker if enabled (being phased out)
    worker_task = None
    if settings.WORKER_ENABLED:
        log.warning("Worker mode is deprecated - consider using CLI-style service")
        worker = await get_worker()
        worker_task = asyncio.create_task(worker.start())
        background_tasks.add(worker_task)
        worker_task.add_done_callback(background_tasks.discard)
        log.info("Worker started")

    # Start SSE manager if enabled
    if settings.ENABLE_SSE:
        sse_manager = await get_sse_manager()
        log.info("SSE manager started")

    if settings.MQTT_ENABLED and not settings.WORKER_ENABLED:
        mqtt_client = get_mqtt_client()
        await mqtt_client.connect()

        async def mqtt_publisher_task() -> None:
            consecutive_failures = 0
            max_consecutive_failures = 10
            backoff_base = 2.0
            max_backoff = 300.0  # 5 minutes
            while True:
                try:
                    await asyncio.sleep(settings.MQTT_PUBLISH_INTERVAL)
                    log.info("Periodic MQTT update triggered.")
                    client = get_client()
                    lock = get_lock()
                    async with lock, client.connection():
                        status = await client.get_status_data()

                    # Update cache if enabled
                    if settings.ENABLE_CACHE:
                        cache = await get_cache()
                        await cache.update(status, source="poll")

                    await mqtt_client.publish_status(status)
                    consecutive_failures = 0  # Reset on success
                except asyncio.CancelledError:
                    log.info("MQTT publisher task cancelled")
                    raise
                except Exception as e:
                    consecutive_failures += 1
                    log.error(
                        f"Error in MQTT publisher task ({consecutive_failures}/{max_consecutive_failures}): {e}",
                        exc_info=True,
                    )
                    if consecutive_failures >= max_consecutive_failures:
                        log.error(
                            f"MQTT publisher task failed {max_consecutive_failures} times, stopping"
                        )
                        break

                    # Exponential backoff
                    backoff_time = min(backoff_base**consecutive_failures, max_backoff)
                    log.info(f"Backing off for {backoff_time:.1f}s before retry")
                    await asyncio.sleep(backoff_time)

        task = asyncio.create_task(mqtt_publisher_task())
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)

    yield
    # Shutdown
    log.info("Shutting down pycz2 API server...")

    # Stop HVAC service if running
    if not settings.WORKER_ENABLED:
        await shutdown_hvac_service()
        log.info("HVAC service stopped")

    # Stop worker if running
    if settings.WORKER_ENABLED:
        worker = await get_worker()
        await worker.stop()
        log.info("Worker stopped")

    # Stop SSE manager if running
    if settings.ENABLE_SSE:
        sse_manager = await get_sse_manager()
        await sse_manager.stop()
        log.info("SSE manager stopped")

    # Cancel all background tasks
    for task in background_tasks:
        task.cancel()

    # Wait for all tasks to complete cancellation
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


async def get_status_and_publish(
    client: ComfortZoneIIClient,
    mqtt_client: MqttClient | None = None,
) -> SystemStatus:
    """Helper to get status and publish to MQTT if enabled."""
    async with client.connection():
        try:
            status = await client.get_status_data()
            if settings.MQTT_ENABLED and mqtt_client:
                await mqtt_client.publish_status(status)
            return status
        except RetryError as e:
            log.error(
                f"Failed to communicate with HVAC controller after multiple retries: {e}"
            )
            raise HTTPException(
                status_code=504, detail="Could not communicate with HVAC controller."
            ) from e
        except Exception as e:
            log.error(f"An unexpected error occurred: {e}", exc_info=True)
            raise HTTPException(
                status_code=500, detail="An internal server error occurred."
            ) from e


@app.get("/status")
async def get_current_status(
    request: Request,
    client: ComfortZoneIIClient = Depends(get_client),
    lock: asyncio.Lock = Depends(get_lock),
) -> dict:
    """
    Get the current system status.

    Query parameters:
    - flat=1: Return legacy flat response format (for backwards compatibility)
    - force=true: Force refresh from HVAC (bypass cache)
    """
    # Check for compatibility mode
    use_flat_format = request.query_params.get("flat") == "1"
    force_refresh = request.query_params.get("force") == "true"
    raw_requested = _is_truthy(request.query_params.get("raw"))

    if settings.ENABLE_CACHE and not settings.WORKER_ENABLED:
        # Use HVAC service for CLI-style operations
        service = await get_hvac_service()
        status, meta = await service.get_status(
            force_refresh=force_refresh, include_raw=raw_requested
        )

        if use_flat_format:
            # Legacy flat format - just the status data
            return _status_payload(status, include_raw=raw_requested, flat=True)
        else:
            # New structured format with metadata
            return {
                "status": _status_payload(status, include_raw=raw_requested),
                "meta": meta.to_dict(),
            }
    elif settings.ENABLE_CACHE:
        # Return from cache immediately
        cache = await get_cache()
        status, meta = await cache.get()
        if raw_requested and (status is None or status.raw is None):
            # Raw data not present; cannot satisfy request in worker mode
            log.warning("Raw status requested but not available in cache")

        if use_flat_format:
            # Legacy flat format - just the status data
            return _status_payload(status, include_raw=raw_requested, flat=True)
        else:
            # New structured format with metadata
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
                    # Legacy flat format
                    return _status_payload(status, include_raw=raw_requested, flat=True)
                else:
                    # New format (even without cache, provide minimal meta)
                    return {
                        "status": _status_payload(status, include_raw=raw_requested),
                        "meta": {
                            "connected": True,
                            "is_stale": False,
                            "source": "direct",
                        },
                    }
            except RetryError as e:
                log.error(f"Failed to get status: {e}")
                raise HTTPException(
                    status_code=504,
                    detail="Could not communicate with HVAC controller.",
                ) from e


@app.post("/update")
async def force_update_and_publish(
    client: ComfortZoneIIClient = Depends(get_client),
    mqtt_client: MqttClient = Depends(get_mqtt_client),
    lock: asyncio.Lock = Depends(get_lock),
) -> dict:
    """
    Force a status refresh from the HVAC system and publish it to MQTT.
    This replaces the periodic trigger from Node-RED.
    """
    try:
        if not settings.WORKER_ENABLED:
            # Use HVAC service for CLI-style operations
            service = await get_hvac_service()
            status, meta = await service.get_status(force_refresh=True)

            # Publish to MQTT if enabled and we got a status
            if settings.MQTT_ENABLED and status:
                await mqtt_client.publish_status(status)

            return {
                "status": _status_payload(status),
                "meta": meta.to_dict(),
                "message": "Status refreshed successfully",
            }
        elif settings.WORKER_ENABLED:
            # Get current state (will be refreshed by worker)
            cache = await get_cache()
            current_status, _ = await cache.get()

            # Use worker queue to force a refresh
            worker = await get_worker()
            cmd_status = await worker.enqueue_command(
                CommandType.POLL_STATUS,
                {},
                priority=2,  # Medium priority for refresh
            )

            # Return 202 with current state (will be updated via SSE)
            return JSONResponse(
                status_code=202,
                content={
                    "command_id": cmd_status.id,
                    "status": cmd_status.status,
                    "message": "Status refresh queued",
                    "current_state": _status_payload(current_status)
                    if current_status
                    else None,
                    "check_status_at": f"/commands/{cmd_status.id}",
                },
            )
        else:
            # Worker disabled - execute synchronously (legacy)
            async with lock, client.connection():
                status = await client.get_status_data()

            # Update cache if enabled
            if settings.ENABLE_CACHE:
                cache = await get_cache()
                await cache.update(status, source="manual")

            if settings.MQTT_ENABLED:
                await mqtt_client.publish_status(status)

            # Return synchronous result for legacy mode
            if settings.ENABLE_CACHE:
                _, meta = await cache.get()
                return {"status": _status_payload(status), "meta": meta.to_dict()}
            else:
                return {"status": _status_payload(status)}

    except asyncio.QueueFull:
        raise HTTPException(429, "Command queue full, try again later")
    except Exception as e:
        log.error(f"Failed to update status: {e}")
        if settings.ENABLE_CACHE:
            cache = await get_cache()
            await cache.update(None, source="error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/system/mode")
async def set_system_mode(
    args: SystemModeArgs,
    client: ComfortZoneIIClient = Depends(get_client),
    mqtt_client: MqttClient = Depends(get_mqtt_client),
    lock: asyncio.Lock = Depends(get_lock),
) -> dict:
    """Set the main system mode (heat, cool, auto, etc.)."""
    try:
        if not settings.WORKER_ENABLED:
            # Use HVAC service for CLI-style operations
            service = await get_hvac_service()
            await service.execute_command(
                "set_system_mode", mode=args.mode, all_zones=args.all
            )

            # Retrieve latest status/meta from cache (service updated it)
            status_obj, meta = await service.get_status(force_refresh=False)

            # Publish to MQTT if enabled
            if settings.MQTT_ENABLED and status_obj:
                await mqtt_client.publish_status(status_obj)

            return {
                "status": _status_payload(status_obj),
                "meta": meta.to_dict(),
                "message": f"System mode set to {args.mode}",
            }
        elif settings.WORKER_ENABLED:
            # Get current state for provisional calculation
            cache = await get_cache()
            current_status, _ = await cache.get()

            # Use worker queue (non-blocking)
            worker = await get_worker()
            cmd_status = await worker.enqueue_command(
                CommandType.SET_SYSTEM_MODE,
                {"mode": args.mode, "all_zones_mode": args.all},
                priority=1,  # High priority for user commands
            )

            # Calculate provisional state
            provisional = calculate_provisional_state(
                current_status, CommandType.SET_SYSTEM_MODE, cmd_status.args
            )

            # Return 202 with command info
            return JSONResponse(
                status_code=202,
                content={
                    "command_id": cmd_status.id,
                    "status": cmd_status.status,
                    "provisional_state": provisional,
                    "check_status_at": f"/commands/{cmd_status.id}",
                },
            )
        else:
            # Worker disabled - execute synchronously (legacy)
            async with lock, client.connection():
                await client.set_system_mode(mode=args.mode, all_zones_mode=args.all)
                status = await client.get_status_data()

            # Update cache if enabled
            if settings.ENABLE_CACHE:
                cache = await get_cache()
                await cache.update(status, source="writeback")

            if settings.MQTT_ENABLED:
                await mqtt_client.publish_status(status)

            # Return synchronous result for legacy mode
            if settings.ENABLE_CACHE:
                _, meta = await cache.get()
                return {"status": _status_payload(status), "meta": meta.to_dict()}
            else:
                return {"status": _status_payload(status)}

    except asyncio.QueueFull:
        raise HTTPException(429, "Command queue full, try again later")
    except Exception as e:
        log.error(f"Failed to set system mode: {e}")
        if settings.ENABLE_CACHE:
            cache = await get_cache()
            await cache.update(None, source="error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/system/fan")
async def set_system_fan(
    args: SystemFanArgs,
    client: ComfortZoneIIClient = Depends(get_client),
    mqtt_client: MqttClient = Depends(get_mqtt_client),
    lock: asyncio.Lock = Depends(get_lock),
) -> dict:
    """Set the system fan mode (auto, on)."""
    try:
        if not settings.WORKER_ENABLED:
            # Use HVAC service for CLI-style operations
            service = await get_hvac_service()
            await service.execute_command("set_fan_mode", fan_mode=args.fan)

            status_obj, meta = await service.get_status(force_refresh=False)

            # Publish to MQTT if enabled
            if settings.MQTT_ENABLED and status_obj:
                await mqtt_client.publish_status(status_obj)

            return {
                "status": _status_payload(status_obj),
                "meta": meta.to_dict(),
                "message": f"Fan mode set to {args.fan}",
            }
        elif settings.WORKER_ENABLED:
            # Get current state for provisional calculation
            cache = await get_cache()
            current_status, _ = await cache.get()

            # Use worker queue (non-blocking)
            worker = await get_worker()
            cmd_status = await worker.enqueue_command(
                CommandType.SET_FAN_MODE,
                {"fan": args.fan},
                priority=1,  # High priority for user commands
            )

            # Calculate provisional state
            provisional = calculate_provisional_state(
                current_status,
                CommandType.SET_FAN_MODE,
                {"mode": args.fan},  # Note: provisional expects 'mode' key
            )

            # Return 202 with command info
            return JSONResponse(
                status_code=202,
                content={
                    "command_id": cmd_status.id,
                    "status": cmd_status.status,
                    "provisional_state": provisional,
                    "check_status_at": f"/commands/{cmd_status.id}",
                },
            )
        else:
            # Worker disabled - execute synchronously (legacy)
            async with lock, client.connection():
                await client.set_fan_mode(args.fan)
                status = await client.get_status_data()

            # Update cache if enabled
            if settings.ENABLE_CACHE:
                cache = await get_cache()
                await cache.update(status, source="writeback")

            if settings.MQTT_ENABLED:
                await mqtt_client.publish_status(status)

            # Return synchronous result for legacy mode
            if settings.ENABLE_CACHE:
                _, meta = await cache.get()
                return {"status": _status_payload(status), "meta": meta.to_dict()}
            else:
                return {"status": _status_payload(status)}

    except asyncio.QueueFull:
        raise HTTPException(429, "Command queue full, try again later")
    except Exception as e:
        log.error(f"Failed to set fan mode: {e}")
        if settings.ENABLE_CACHE:
            cache = await get_cache()
            await cache.update(None, source="error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/zones/batch/temperature")
async def set_batch_zone_temperature(
    args: BatchZoneTemperatureArgs,
    client: ComfortZoneIIClient = Depends(get_client),
    mqtt_client: MqttClient = Depends(get_mqtt_client),
    lock: asyncio.Lock = Depends(get_lock),
) -> dict:
    """
    Set the heating and/or cooling setpoints for multiple zones at once.
    This is more efficient than calling /zones/{zone_id}/temperature multiple times,
    as it performs the update in a single transaction.

    You must also set `hold` or `temp` to true for the change to stick.
    """
    # Validate all zone IDs
    for zone_id in args.zones:
        if not 1 <= zone_id <= settings.CZ_ZONES:
            raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found.")

    # Remove duplicates
    zones = list(set(args.zones))

    try:
        if not settings.WORKER_ENABLED:
            # Use HVAC service for CLI-style operations
            service = await get_hvac_service()
            await service.execute_command(
                "set_zone_setpoints",
                zones=zones,
                heat_setpoint=args.heat,
                cool_setpoint=args.cool,
                temporary_hold=args.temp,
                hold=args.hold,
                out_mode=args.out,
            )

            status_obj, meta = await service.get_status(force_refresh=False)

            # Publish to MQTT if enabled
            if settings.MQTT_ENABLED and status_obj:
                await mqtt_client.publish_status(status_obj)

            zone_list = ", ".join(map(str, sorted(zones)))
            return {
                "status": _status_payload(status_obj),
                "meta": meta.to_dict(),
                "message": f"Zones {zone_list} temperature updated",
            }
        elif settings.WORKER_ENABLED:
            # Get current state for provisional calculation
            cache = await get_cache()
            current_status, _ = await cache.get()

            # Use worker queue (non-blocking)
            worker = await get_worker()
            cmd_status = await worker.enqueue_command(
                CommandType.SET_ZONE_TEMPERATURE,
                {
                    "zones": zones,
                    "heat_setpoint": args.heat,
                    "cool_setpoint": args.cool,
                    "temporary_hold": args.temp,
                    "hold": args.hold,
                    "out_mode": args.out,
                },
                priority=1,  # High priority for user commands
            )

            # Calculate provisional state
            provisional = calculate_provisional_state(
                current_status, CommandType.SET_ZONE_TEMPERATURE, cmd_status.args
            )

            # Return 202 with command info
            return JSONResponse(
                status_code=202,
                content={
                    "command_id": cmd_status.id,
                    "status": cmd_status.status,
                    "provisional_state": provisional,
                    "check_status_at": f"/commands/{cmd_status.id}",
                },
            )
        else:
            # Legacy path (direct connection)
            async with lock, client.connection():
                await client.set_zone_setpoints(
                    zones=zones,
                    heat_setpoint=args.heat,
                    cool_setpoint=args.cool,
                    temporary_hold=args.temp,
                    hold=args.hold,
                    out_mode=args.out,
                )
                status = await client.get_status_data()

            # Update cache if enabled
            if settings.ENABLE_CACHE:
                cache = await get_cache()
                await cache.update(status, source="writeback")

            if settings.MQTT_ENABLED:
                await mqtt_client.publish_status(status)

            # Return synchronous result
            if settings.ENABLE_CACHE:
                _, meta = await cache.get()
                return {"status": _status_payload(status), "meta": meta.to_dict()}
            else:
                return {"status": _status_payload(status)}

    except asyncio.QueueFull:
        raise HTTPException(429, "Command queue full, try again later")
    except Exception as e:
        log.error(f"Failed to set batch zone temperature: {e}")
        if settings.ENABLE_CACHE:
            cache = await get_cache()
            await cache.update(None, source="error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/zones/{zone_id}/temperature")
async def set_zone_temperature(
    zone_id: int,
    args: ZoneTemperatureArgs,
    client: ComfortZoneIIClient = Depends(get_client),
    mqtt_client: MqttClient = Depends(get_mqtt_client),
    lock: asyncio.Lock = Depends(get_lock),
) -> dict:
    """
    Set the heating and/or cooling setpoints for a specific zone.
    You must also set `hold` or `temp` to true for the change to stick.
    """
    if not 1 <= zone_id <= settings.CZ_ZONES:
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found.")

    try:
        if not settings.WORKER_ENABLED:
            # Use HVAC service for CLI-style operations
            service = await get_hvac_service()
            await service.execute_command(
                "set_zone_setpoints",
                zones=[zone_id],
                heat_setpoint=args.heat,
                cool_setpoint=args.cool,
                temporary_hold=args.temp,
                hold=args.hold,
                out_mode=args.out,
            )

            status_obj, meta = await service.get_status(force_refresh=False)

            # Publish to MQTT if enabled
            if settings.MQTT_ENABLED and status_obj:
                await mqtt_client.publish_status(status_obj)

            return {
                "status": _status_payload(status_obj),
                "meta": meta.to_dict(),
                "message": f"Zone {zone_id} temperature updated",
            }
        elif settings.WORKER_ENABLED:
            # Get current state for provisional calculation
            cache = await get_cache()
            current_status, _ = await cache.get()

            # Use worker queue (non-blocking)
            worker = await get_worker()
            cmd_status = await worker.enqueue_command(
                CommandType.SET_ZONE_TEMPERATURE,
                {
                    "zones": [zone_id],
                    "heat_setpoint": args.heat,
                    "cool_setpoint": args.cool,
                    "temporary_hold": args.temp,
                    "hold": args.hold,
                    "out_mode": args.out,
                },
                priority=1,  # High priority for user commands
            )

            # Calculate provisional state
            provisional = calculate_provisional_state(
                current_status, CommandType.SET_ZONE_TEMPERATURE, cmd_status.args
            )

            # Return 202 with command info
            return JSONResponse(
                status_code=202,
                content={
                    "command_id": cmd_status.id,
                    "status": cmd_status.status,
                    "provisional_state": provisional,
                    "check_status_at": f"/commands/{cmd_status.id}",
                },
            )
        else:
            # Worker disabled - execute synchronously (legacy)
            async with lock, client.connection():
                await client.set_zone_setpoints(
                    zones=[zone_id],
                    heat_setpoint=args.heat,
                    cool_setpoint=args.cool,
                    temporary_hold=args.temp,
                    hold=args.hold,
                    out_mode=args.out,
                )
                status = await client.get_status_data()

            # Update cache if enabled
            if settings.ENABLE_CACHE:
                cache = await get_cache()
                await cache.update(status, source="writeback")

            if settings.MQTT_ENABLED:
                await mqtt_client.publish_status(status)

            # Return synchronous result for legacy mode
            if settings.ENABLE_CACHE:
                _, meta = await cache.get()
                return {"status": _status_payload(status), "meta": meta.to_dict()}
            else:
                return {"status": _status_payload(status)}

    except asyncio.QueueFull:
        raise HTTPException(429, "Command queue full, try again later")
    except Exception as e:
        log.error(f"Failed to set zone temperature: {e}")
        if settings.ENABLE_CACHE:
            cache = await get_cache()
            await cache.update(None, source="error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/zones/{zone_id}/hold")
async def set_zone_hold(
    zone_id: int,
    args: ZoneHoldArgs,
    client: ComfortZoneIIClient = Depends(get_client),
    mqtt_client: MqttClient = Depends(get_mqtt_client),
    lock: asyncio.Lock = Depends(get_lock),
) -> dict:
    """Set or release the hold/temporary status for a zone."""
    if not 1 <= zone_id <= settings.CZ_ZONES:
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found.")

    try:
        if not settings.WORKER_ENABLED:
            # Use HVAC service for CLI-style operations
            service = await get_hvac_service()
            await service.execute_command(
                "set_zone_setpoints",
                zones=[zone_id],
                hold=args.hold,
                temporary_hold=args.temp,
            )

            status_obj, meta = await service.get_status(force_refresh=False)

            # Publish to MQTT if enabled
            if settings.MQTT_ENABLED and status_obj:
                await mqtt_client.publish_status(status_obj)

            return {
                "status": _status_payload(status_obj),
                "meta": meta.to_dict(),
                "message": f"Zone {zone_id} hold settings updated",
            }
        elif settings.WORKER_ENABLED:
            # Get current state for provisional calculation
            cache = await get_cache()
            current_status, _ = await cache.get()

            # Use worker queue (non-blocking)
            worker = await get_worker()
            cmd_status = await worker.enqueue_command(
                CommandType.SET_ZONE_HOLD,
                {"zones": [zone_id], "hold": args.hold, "temporary_hold": args.temp},
                priority=1,  # High priority for user commands
            )

            # Calculate provisional state
            provisional = calculate_provisional_state(
                current_status, CommandType.SET_ZONE_HOLD, cmd_status.args
            )

            # Return 202 with command info
            return JSONResponse(
                status_code=202,
                content={
                    "command_id": cmd_status.id,
                    "status": cmd_status.status,
                    "provisional_state": provisional,
                    "check_status_at": f"/commands/{cmd_status.id}",
                },
            )
        else:
            # Worker disabled - execute synchronously (legacy)
            async with lock, client.connection():
                await client.set_zone_setpoints(
                    zones=[zone_id], hold=args.hold, temporary_hold=args.temp
                )
                status = await client.get_status_data()

            # Update cache if enabled
            if settings.ENABLE_CACHE:
                cache = await get_cache()
                await cache.update(status, source="writeback")

            if settings.MQTT_ENABLED:
                await mqtt_client.publish_status(status)

            # Return synchronous result for legacy mode
            if settings.ENABLE_CACHE:
                _, meta = await cache.get()
                return {"status": _status_payload(status), "meta": meta.to_dict()}
            else:
                return {"status": _status_payload(status)}

    except asyncio.QueueFull:
        raise HTTPException(429, "Command queue full, try again later")
    except Exception as e:
        log.error(f"Failed to set zone hold: {e}")
        if settings.ENABLE_CACHE:
            cache = await get_cache()
            await cache.update(None, source="error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# Monitoring and admin endpoints


@app.get("/status/live")
async def get_live_status(
    client: ComfortZoneIIClient = Depends(get_client),
    lock: asyncio.Lock = Depends(get_lock),
) -> dict:
    """
    Get live status directly from HVAC (bypasses cache).
    Useful for debugging and admin purposes.
    """
    try:
        async with lock, client.connection():
            status = await client.get_status_data()

        # Optionally update cache with fresh data
        if settings.ENABLE_CACHE:
            cache = await get_cache()
            await cache.update(status, source="live_query")

        return {
            "status": _status_payload(status),
            "source": "live",
            "timestamp": time.time(),
        }
    except RetryError as e:
        log.error(f"Failed to get live status: {e}")
        raise HTTPException(
            status_code=504, detail="Could not communicate with HVAC controller."
        ) from e
    except Exception as e:
        log.error(f"Unexpected error getting live status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cache/stats")
async def get_cache_stats() -> dict:
    """Get cache statistics for monitoring."""
    if not settings.ENABLE_CACHE:
        raise HTTPException(status_code=404, detail="Cache is not enabled")

    cache = await get_cache()
    stats = await cache.get_stats()
    return stats


@app.post("/cache/clear")
async def clear_cache() -> dict:
    """Clear the cache (admin endpoint)."""
    if not settings.ENABLE_CACHE:
        raise HTTPException(status_code=404, detail="Cache is not enabled")

    cache = await get_cache()
    await cache.clear()
    return {"message": "Cache cleared successfully"}


@app.get("/health")
async def health_check() -> dict:
    """
    Health check endpoint for monitoring and load balancers.
    Returns system health status and metrics.
    """
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "features": {
            "cache_enabled": settings.ENABLE_CACHE,
            "mqtt_enabled": settings.MQTT_ENABLED,
            "sse_enabled": settings.ENABLE_SSE,
            "worker_enabled": settings.WORKER_ENABLED,
        },
    }

    # Add cache health if enabled
    if settings.ENABLE_CACHE:
        cache = await get_cache()
        cache_stats = await cache.get_stats()
        health_status["cache"] = {
            "connected": cache_stats["connected"],
            "has_data": cache_stats["has_data"],
            "is_stale": cache_stats["is_stale"],
            "age_seconds": cache_stats.get("age_seconds"),
        }

        # Mark as degraded if cache is stale or disconnected
        if cache_stats["is_stale"] or not cache_stats["connected"]:
            health_status["status"] = "degraded"

    # Add worker health if enabled
    if settings.WORKER_ENABLED:
        try:
            worker = await get_worker()
            worker_stats = worker.get_stats()
            health_status["worker"] = {
                "connected": worker_stats["connected"],
                "connection_state": worker_stats["connection_state"],
                "queue_size": worker_stats["queue_size"],
                "commands_processed": worker_stats["commands_processed"],
            }

            # Mark as degraded if worker is not connected
            if not worker_stats["connected"]:
                health_status["status"] = "degraded"
        except Exception as e:
            log.error(f"Failed to get worker stats: {e}")
            health_status["worker"] = {"error": str(e)}
            health_status["status"] = "degraded"

    # Check background tasks
    health_status["background_tasks"] = {
        "active": len(background_tasks),
        "running": all(not task.done() for task in background_tasks),
    }

    if not health_status["background_tasks"]["running"]:
        health_status["status"] = "unhealthy"

    return health_status


@app.get("/commands/{command_id}")
async def get_command_status(command_id: str) -> dict:
    """
    Get status of a submitted command.

    Returns command execution status including result or error.
    """
    if not settings.WORKER_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Worker is not enabled, command tracking unavailable",
        )

    worker = await get_worker()
    status = await worker.tracker.get(command_id)

    if not status:
        raise HTTPException(status_code=404, detail="Command not found or expired")

    return {
        "id": status.id,
        "type": status.type.value,
        "status": status.status,
        "created_at": status.created_at,
        "completed_at": status.completed_at,
        "result": status.result,
        "error": status.error,
        "cache_version": status.cache_version,
    }


@app.get("/worker/stats")
async def get_worker_stats() -> dict:
    """Get detailed worker statistics."""
    if not settings.WORKER_ENABLED:
        raise HTTPException(status_code=404, detail="Worker is not enabled")

    worker = await get_worker()
    return worker.get_stats()


@app.get("/events")
async def events(request: Request):
    """
    Server-Sent Events endpoint for real-time updates.

    Clients can connect to this endpoint to receive real-time
    status updates as they occur, eliminating the need for polling.
    """
    if not settings.ENABLE_SSE:
        raise HTTPException(status_code=404, detail="SSE is not enabled")

    try:
        return await create_sse_response(request)
    except ValueError as e:
        raise HTTPException(status_code=429, detail=str(e))


@app.get("/sse/stats")
async def get_sse_stats() -> dict:
    """Get SSE manager statistics."""
    if not settings.ENABLE_SSE:
        raise HTTPException(status_code=404, detail="SSE is not enabled")

    sse_manager = await get_sse_manager()
    return sse_manager.get_stats()
