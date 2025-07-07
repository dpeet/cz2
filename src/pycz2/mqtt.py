# src/pycz2/mqtt.py
import logging
from functools import lru_cache

import asyncio_mqtt as mqtt

from .config import settings
from .core.models import SystemStatus

log = logging.getLogger(__name__)


class MqttClient:
    def __init__(self):
        self._client = mqtt.Client(
            hostname=settings.MQTT_HOST,
            port=settings.MQTT_PORT,
            username=settings.MQTT_USER,
            password=settings.MQTT_PASSWORD,
        )
        self.status_topic = f"{settings.MQTT_TOPIC_PREFIX}/status"

    async def connect(self):
        try:
            await self._client.connect()
            log.info(f"Connected to MQTT broker at {settings.MQTT_HOST}:{settings.MQTT_PORT}")
        except Exception as e:
            log.error(f"Failed to connect to MQTT broker: {e}")
            # Depending on requirements, you might want to retry or exit
            raise

    async def disconnect(self):
        await self._client.disconnect()
        log.info("Disconnected from MQTT broker.")

    async def publish_status(self, status: SystemStatus):
        if not settings.MQTT_ENABLED:
            return
        try:
            payload = status.model_dump_json()
            await self._client.publish(self.status_topic, payload=payload, qos=1)
            log.info(f"Published status to MQTT topic: {self.status_topic}")
        except Exception as e:
            log.error(f"Failed to publish to MQTT: {e}")


@lru_cache
def get_mqtt_client() -> MqttClient:
    return MqttClient()
