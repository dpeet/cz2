# src/pycz2/mqtt.py
import logging
from functools import lru_cache

import aiomqtt as mqtt

from .config import settings
from .core.models import SystemStatus

log = logging.getLogger(__name__)


class MqttClient:
    def __init__(self) -> None:
        self._client: mqtt.Client | None = None
        self._hostname = settings.MQTT_HOST
        self._port = settings.MQTT_PORT
        self._username = settings.MQTT_USER
        self._password = settings.MQTT_PASSWORD
        self.status_topic = f"{settings.MQTT_TOPIC_PREFIX}/status"

    async def connect(self) -> None:
        try:
            self._client = mqtt.Client(
                hostname=self._hostname,
                port=self._port,
                username=self._username,
                password=self._password,
            )
            await self._client.__aenter__()
            log.info(
                f"Connected to MQTT broker at {self._hostname}:{self._port}"
            )
        except Exception as e:
            log.error(f"Failed to connect to MQTT broker: {e}")
            raise

    async def disconnect(self) -> None:
        if self._client:
            await self._client.__aexit__(None, None, None)
            self._client = None
            log.info("Disconnected from MQTT broker.")

    async def publish_status(self, status: SystemStatus) -> None:
        """
        Publish system status to MQTT broker.

        Uses flat format for backwards compatibility with legacy frontend.
        """
        if not settings.MQTT_ENABLED or not self._client:
            return
        try:
            # Use flat format to match legacy MQTT payload structure
            payload = status.to_json(flat=True)
            # Retain last known status for immediate delivery to new subscribers
            await self._client.publish(self.status_topic, payload=payload, qos=1, retain=True)
            log.info(f"Published status to MQTT topic: {self.status_topic}")
        except Exception as e:
            log.error(f"Failed to publish to MQTT: {e}")


@lru_cache
def get_mqtt_client() -> MqttClient:
    return MqttClient()
