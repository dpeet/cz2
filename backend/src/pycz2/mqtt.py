# src/pycz2/mqtt.py
import asyncio
import json
import logging
from typing import Any

import aiomqtt as mqtt

from .config import settings
from .core.models import SystemStatus
from .healthcheck import send_healthcheck_ping

log = logging.getLogger(__name__)


class MqttClient:
    def __init__(self) -> None:
        self._client: mqtt.Client | None = None
        self._lock = asyncio.Lock()
        self._hostname = settings.MQTT_HOST
        self._port = settings.MQTT_PORT
        self._username = settings.MQTT_USER
        self._password = settings.MQTT_PASSWORD
        self.status_topic = f"{settings.MQTT_TOPIC_PREFIX}/status"
        self.audit_topic = f"{settings.MQTT_TOPIC_PREFIX}/audit"
        self._connected = False

    async def connect(self) -> None:
        """Connect to MQTT broker. No-op if already connected."""
        async with self._lock:
            if self._connected and self._client:
                return
            await self._connect_unlocked()

    async def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        async with self._lock:
            await self._disconnect_unlocked()

    async def publish_status(self, status: SystemStatus) -> None:
        """Publish system status to MQTT broker."""
        if not settings.MQTT_ENABLED:
            return

        payload = status.to_json(flat=True)
        published = False

        async with self._lock:
            try:
                if not await self._ensure_connected():
                    return
                assert self._client is not None
                await self._client.publish(
                    self.status_topic, payload=payload, qos=1, retain=True,
                )
                published = True
                log.info(f"Published status to MQTT topic: {self.status_topic}")
            except mqtt.MqttError as e:
                self._connected = False
                log.error(f"MQTT error, will reconnect on next publish: {e}")
            except Exception as e:
                self._connected = False
                log.error(f"Failed to publish to MQTT: {e}")

        # Fire-and-forget healthcheck (outside lock)
        if published and settings.HEALTHCHECK_UUID:
            asyncio.create_task(send_healthcheck_ping())

    async def publish_audit(self, payload: dict[str, Any]) -> None:
        """Publish an audit event to MQTT broker."""
        if not settings.MQTT_ENABLED:
            return

        data = json.dumps(payload)

        async with self._lock:
            try:
                if not await self._ensure_connected():
                    return
                assert self._client is not None
                await self._client.publish(
                    self.audit_topic, payload=data, qos=1, retain=False,
                )
                log.info(f"Published audit to MQTT topic: {self.audit_topic}")
            except mqtt.MqttError as e:
                self._connected = False
                log.error(f"MQTT audit publish error, will reconnect on next publish: {e}")
            except Exception as e:
                self._connected = False
                log.error(f"Failed to publish audit to MQTT: {e}")

    # -- Private helpers (caller must hold self._lock) --

    async def _ensure_connected(self) -> bool:
        """Reconnect if needed. Caller must hold self._lock."""
        if self._connected and self._client:
            return True
        log.info("MQTT client not connected, attempting to reconnect...")
        try:
            await self._cleanup_unlocked()
            await self._connect_unlocked()
            return True
        except Exception as e:
            log.error(f"Failed to reconnect to MQTT broker: {e}")
            return False

    async def _connect_unlocked(self) -> None:
        """Create and enter a new MQTT client. Caller must hold self._lock."""
        self._client = mqtt.Client(
            hostname=self._hostname,
            port=self._port,
            username=self._username,
            password=self._password,
        )
        await self._client.__aenter__()
        self._connected = True
        log.info(f"Connected to MQTT broker at {self._hostname}:{self._port}")

    async def _disconnect_unlocked(self) -> None:
        """Clean exit of MQTT client. Caller must hold self._lock."""
        if self._client:
            try:
                await self._client.__aexit__(None, None, None)
            except Exception as e:
                log.warning(f"Error during MQTT disconnect: {e}")
            self._client = None
            self._connected = False
            log.info("Disconnected from MQTT broker.")

    async def _cleanup_unlocked(self) -> None:
        """Force-close a stale client. Caller must hold self._lock."""
        if self._client:
            try:
                await self._client.__aexit__(None, None, None)
            except Exception:
                pass
            self._client = None


_mqtt_client: MqttClient | None = None


def get_mqtt_client() -> MqttClient:
    global _mqtt_client
    if _mqtt_client is None:
        _mqtt_client = MqttClient()
    return _mqtt_client
