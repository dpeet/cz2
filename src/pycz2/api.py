# src/pycz2/api.py
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from tenacity import RetryError

from .config import settings
from .core.client import ComfortZoneIIClient, get_client, get_lock
from .core.models import (
    SystemFanArgs,
    SystemModeArgs,
    SystemStatus,
    ZoneHoldArgs,
    ZoneTemperatureArgs,
)
from .mqtt import MqttClient, get_mqtt_client

log = logging.getLogger(__name__)

# Global state to hold the background task
background_tasks = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    log.info("Starting pycz2 API server...")
    if settings.MQTT_ENABLED:
        mqtt_client = get_mqtt_client()
        await mqtt_client.connect()

        async def mqtt_publisher_task():
            while True:
                try:
                    await asyncio.sleep(settings.MQTT_PUBLISH_INTERVAL)
                    log.info("Periodic MQTT update triggered.")
                    client = get_client()
                    lock = get_lock()
                    async with lock:
                        status = await client.get_status_data()
                    await mqtt_client.publish_status(status)
                except Exception as e:
                    log.error(f"Error in MQTT publisher task: {e}")

        task = asyncio.create_task(mqtt_publisher_task())
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)

    yield
    # Shutdown
    log.info("Shutting down pycz2 API server...")
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


async def get_status_and_publish(
    client: ComfortZoneIIClient, mqtt_client: MqttClient
) -> SystemStatus:
    """Helper to get status and publish to MQTT if enabled."""
    try:
        status = await client.get_status_data()
        if settings.MQTT_ENABLED:
            await mqtt_client.publish_status(status)
        return status
    except RetryError as e:
        log.error(f"Failed to communicate with HVAC controller after multiple retries: {e}")
        raise HTTPException(status_code=504, detail="Could not communicate with HVAC controller.")
    except Exception as e:
        log.error(f"An unexpected error occurred: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal server error occurred.")


@app.get("/status", response_model=SystemStatus)
async def get_current_status(client: ComfortZoneIIClient = Depends(get_client), lock: asyncio.Lock = Depends(get_lock)):
    """Get the current system status."""
    async with lock:
        try:
            return await client.get_status_data()
        except RetryError as e:
            log.error(f"Failed to get status: {e}")
            raise HTTPException(status_code=504, detail="Could not communicate with HVAC controller.")


@app.post("/update", response_model=SystemStatus)
async def force_update_and_publish(
    client: ComfortZoneIIClient = Depends(get_client),
    mqtt_client: MqttClient = Depends(get_mqtt_client),
    lock: asyncio.Lock = Depends(get_lock),
):
    """
    Force a status refresh from the HVAC system and publish it to MQTT.
    This replaces the periodic trigger from Node-RED.
    """
    async with lock:
        return await get_status_and_publish(client, mqtt_client)


@app.post("/system/mode", response_model=SystemStatus)
async def set_system_mode(
    args: SystemModeArgs,
    client: ComfortZoneIIClient = Depends(get_client),
    mqtt_client: MqttClient = Depends(get_mqtt_client),
    lock: asyncio.Lock = Depends(get_lock),
):
    """Set the main system mode (heat, cool, auto, etc.)."""
    async with lock:
        await client.set_system_mode(mode=args.mode, all_zones_mode=args.all)
        return await get_status_and_publish(client, mqtt_client)


@app.post("/system/fan", response_model=SystemStatus)
async def set_system_fan(
    args: SystemFanArgs,
    client: ComfortZoneIIClient = Depends(get_client),
    mqtt_client: MqttClient = Depends(get_mqtt_client),
    lock: asyncio.Lock = Depends(get_lock),
):
    """Set the system fan mode (auto, on)."""
    async with lock:
        await client.set_fan_mode(args.fan)
        return await get_status_and_publish(client, mqtt_client)


@app.post("/zones/{zone_id}/temperature", response_model=SystemStatus)
async def set_zone_temperature(
    zone_id: int,
    args: ZoneTemperatureArgs,
    client: ComfortZoneIIClient = Depends(get_client),
    mqtt_client: MqttClient = Depends(get_mqtt_client),
    lock: asyncio.Lock = Depends(get_lock),
):
    """
    Set the heating and/or cooling setpoints for a specific zone.
    You must also set `hold` or `temp` to true for the change to stick.
    """
    if not (1 <= zone_id <= settings.CZ_ZONES):
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found.")

    async with lock:
        await client.set_zone_setpoints(
            zones=[zone_id],
            heat_setpoint=args.heat,
            cool_setpoint=args.cool,
            temporary_hold=args.temp,
            hold=args.hold,
            out_mode=args.out,
        )
        return await get_status_and_publish(client, mqtt_client)


@app.post("/zones/{zone_id}/hold", response_model=SystemStatus)
async def set_zone_hold(
    zone_id: int,
    args: ZoneHoldArgs,
    client: ComfortZoneIIClient = Depends(get_client),
    mqtt_client: MqttClient = Depends(get_mqtt_client),
    lock: asyncio.Lock = Depends(get_lock),
):
    """Set or release the hold/temporary status for a zone."""
    if not (1 <= zone_id <= settings.CZ_ZONES):
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found.")

    async with lock:
        await client.set_zone_setpoints(
            zones=[zone_id], hold=args.hold, temporary_hold=args.temp
        )
        return await get_status_and_publish(client, mqtt_client)
