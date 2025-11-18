# src/pycz2/mqtt.py
import asyncio
import logging
from functools import lru_cache

import aiomqtt as mqtt

from .config import settings
from .core.models import SystemStatus
from .healthcheck import send_healthcheck_ping

log = logging.getLogger(__name__)


class MqttClient:
    def __init__(self) -> None:
        self._client: mqtt.Client | None = None
        self._hostname = settings.MQTT_HOST
        self._port = settings.MQTT_PORT
        self._username = settings.MQTT_USER
        self._password = settings.MQTT_PASSWORD
        self.status_topic = f"{settings.MQTT_TOPIC_PREFIX}/status"
        self._connected = False

    async def connect(self) -> None:
        """Connect to MQTT broker."""
        try:
            self._client = mqtt.Client(
                hostname=self._hostname,
                port=self._port,
                username=self._username,
                password=self._password,
            )
            await self._client.__aenter__()
            self._connected = True
            log.info(
                f"Connected to MQTT broker at {self._hostname}:{self._port}"
            )
        except Exception as e:
            self._connected = False
            log.error(f"Failed to connect to MQTT broker: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        if self._client:
            try:
                await self._client.__aexit__(None, None, None)
            except Exception as e:
                log.warning(f"Error during MQTT disconnect: {e}")
            self._client = None
            self._connected = False
            log.info("Disconnected from MQTT broker.")

    async def _ensure_connected(self) -> bool:
        """Ensure we have a valid connection, reconnecting if necessary."""
        if self._connected and self._client:
            return True

        log.info("MQTT client not connected, attempting to reconnect...")
        try:
            # Clean up old client if exists
            if self._client:
                try:
                    await self._client.__aexit__(None, None, None)
                except Exception:
                    pass
                self._client = None

            await self.connect()
            return True
        except Exception as e:
            log.error(f"Failed to reconnect to MQTT broker: {e}")
            return False

    async def publish_status(self, status: SystemStatus) -> None:
        """
        Publish system status to MQTT broker.

        Uses flat format for backwards compatibility with legacy frontend.
        Automatically reconnects if the connection was lost.
        """
        if not settings.MQTT_ENABLED:
            return

        try:
            if not await self._ensure_connected():
                return

            # Use flat format to match legacy MQTT payload structure
            payload = status.to_json(flat=True)
            # Retain last known status for immediate delivery to new subscribers
            await self._client.publish(self.status_topic, payload=payload, qos=1, retain=True)
            log.info(f"Published status to MQTT topic: {self.status_topic}")

            # Send healthcheck ping on successful publish (fire-and-forget)
            if settings.HEALTHCHECK_UUID:
                asyncio.create_task(send_healthcheck_ping())
        except mqtt.MqttError as e:
            self._connected = False
            log.error(f"MQTT error, will reconnect on next publish: {e}")
        except Exception as e:
            self._connected = False
            log.error(f"Failed to publish to MQTT: {e}")


@lru_cache
def get_mqtt_client() -> MqttClient:
    return MqttClient()
