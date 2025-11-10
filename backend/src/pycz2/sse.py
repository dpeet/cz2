# src/pycz2/sse.py
"""
Server-Sent Events (SSE) manager for real-time updates.
"""
import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Set

from fastapi import Request
from sse_starlette.sse import EventSourceResponse

from .cache import get_cache
from .config import settings

log = logging.getLogger(__name__)


class EventType(Enum):
    """Types of SSE events."""
    STATE = "state"          # Full status update
    DELTA = "delta"          # Partial update
    PING = "ping"            # Keepalive
    ERROR = "error"          # Error notification
    COMMAND_RESULT = "result"  # Command execution result
    META = "meta"            # Metadata update only


@dataclass
class SubscriberInfo:
    """Information about an SSE subscriber."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ip_address: str = ""
    connected_at: float = field(default_factory=time.time)
    last_ping: float = field(default_factory=time.time)
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=50))
    user_agent: str = ""
    update_count: int = 0
    error_count: int = 0
    last_event_id: Optional[str] = None


class SSEManager:
    """Manager for SSE connections and event distribution."""

    def __init__(
        self,
        max_subscribers: int = 100,
        max_subscribers_per_ip: int = 5,
        heartbeat_interval: float = 30.0,
        enable_compression: bool = True
    ):
        self.max_subscribers = max_subscribers
        self.max_subscribers_per_ip = max_subscribers_per_ip
        self.heartbeat_interval = heartbeat_interval
        self.enable_compression = enable_compression

        # Subscriber tracking
        self.subscribers: Dict[str, SubscriberInfo] = {}
        self.subscribers_by_ip: Dict[str, Set[str]] = defaultdict(set)
        self._lock = asyncio.Lock()

        # Event ID counter
        self._event_id_counter = 0
        self._event_id_lock = asyncio.Lock()

        # Stats
        self.stats = {
            "total_connections": 0,
            "current_connections": 0,
            "total_events_sent": 0,
            "total_errors": 0,
        }

        # Heartbeat task
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the SSE manager background tasks."""
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            log.info("SSE manager started")

    async def stop(self):
        """Stop the SSE manager."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        # Close all subscriber queues
        async with self._lock:
            for subscriber in self.subscribers.values():
                try:
                    subscriber.queue.put_nowait(None)  # Signal to close
                except asyncio.QueueFull:
                    pass
            self.subscribers.clear()
            self.subscribers_by_ip.clear()

        log.info("SSE manager stopped")

    async def _heartbeat_loop(self):
        """Send periodic heartbeat to all subscribers."""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                await self._send_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Error in heartbeat loop: {e}")

    async def _send_heartbeat(self):
        """Send heartbeat ping to all subscribers."""
        event = {
            "type": EventType.PING.value,
            "timestamp": time.time()
        }
        await self.broadcast_event(EventType.PING, event)

    async def _get_next_event_id(self) -> str:
        """Get the next event ID."""
        async with self._event_id_lock:
            self._event_id_counter += 1
            return str(self._event_id_counter)

    async def subscribe(
        self,
        request: Request,
        last_event_id: Optional[str] = None
    ) -> SubscriberInfo:
        """
        Subscribe a client to SSE updates.

        Args:
            request: The FastAPI request object
            last_event_id: Last event ID received by client (for resume)

        Returns:
            SubscriberInfo object

        Raises:
            ValueError: If max subscribers limit reached
        """
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")

        async with self._lock:
            # Check global limit
            if len(self.subscribers) >= self.max_subscribers:
                raise ValueError("Maximum subscribers limit reached")

            # Check per-IP limit
            ip_subscribers = self.subscribers_by_ip[client_ip]
            if len(ip_subscribers) >= self.max_subscribers_per_ip:
                raise ValueError(f"Maximum subscribers per IP reached for {client_ip}")

            # Create subscriber
            subscriber = SubscriberInfo(
                ip_address=client_ip,
                user_agent=user_agent,
                last_event_id=last_event_id
            )

            # Track subscriber
            self.subscribers[subscriber.id] = subscriber
            self.subscribers_by_ip[client_ip].add(subscriber.id)
            self.stats["total_connections"] += 1
            self.stats["current_connections"] = len(self.subscribers)

            log.info(
                f"New SSE subscriber: {subscriber.id} from {client_ip} "
                f"(total: {len(self.subscribers)})"
            )

        return subscriber

    async def unsubscribe(self, subscriber_id: str):
        """Unsubscribe a client from SSE updates."""
        async with self._lock:
            if subscriber_id in self.subscribers:
                subscriber = self.subscribers[subscriber_id]

                # Remove from tracking
                del self.subscribers[subscriber_id]
                self.subscribers_by_ip[subscriber.ip_address].discard(subscriber_id)

                # Clean up empty IP entries
                if not self.subscribers_by_ip[subscriber.ip_address]:
                    del self.subscribers_by_ip[subscriber.ip_address]

                self.stats["current_connections"] = len(self.subscribers)

                log.info(
                    f"SSE subscriber disconnected: {subscriber_id} "
                    f"(remaining: {len(self.subscribers)})"
                )

    async def broadcast_event(
        self,
        event_type: EventType,
        data: Any,
        event_id: Optional[str] = None
    ):
        """
        Broadcast an event to all subscribers.

        Args:
            event_type: Type of event
            data: Event data (will be JSON serialized)
            event_id: Optional event ID (auto-generated if not provided)
        """
        if event_id is None:
            event_id = await self._get_next_event_id()

        # Format event
        event = {
            "event": event_type.value,
            "id": event_id,
            "data": json.dumps(data) if not isinstance(data, str) else data
        }

        # Send to all subscribers
        dead_subscribers = []
        async with self._lock:
            for subscriber_id, subscriber in self.subscribers.items():
                try:
                    subscriber.queue.put_nowait(event)
                    subscriber.update_count += 1
                    self.stats["total_events_sent"] += 1
                except asyncio.QueueFull:
                    # Queue is full, skip this update
                    log.warning(f"Queue full for subscriber {subscriber_id}, skipping event")
                    subscriber.error_count += 1
                except Exception as e:
                    log.error(f"Error sending to subscriber {subscriber_id}: {e}")
                    subscriber.error_count += 1
                    dead_subscribers.append(subscriber_id)

        # Clean up dead subscribers
        for subscriber_id in dead_subscribers:
            await self.unsubscribe(subscriber_id)

    async def send_to_subscriber(
        self,
        subscriber_id: str,
        event_type: EventType,
        data: Any
    ):
        """Send an event to a specific subscriber."""
        async with self._lock:
            if subscriber_id in self.subscribers:
                subscriber = self.subscribers[subscriber_id]
                event_id = await self._get_next_event_id()

                event = {
                    "event": event_type.value,
                    "id": event_id,
                    "data": json.dumps(data) if not isinstance(data, str) else data
                }

                try:
                    subscriber.queue.put_nowait(event)
                    subscriber.update_count += 1
                except asyncio.QueueFull:
                    log.warning(f"Queue full for subscriber {subscriber_id}")
                    subscriber.error_count += 1

    async def event_generator(
        self,
        subscriber: SubscriberInfo,
        request: Request
    ):
        """
        Generate SSE events for a subscriber.

        This is an async generator that yields events for the SSE response.
        """
        try:
            # Send initial state
            cache = await get_cache()
            status, meta = await cache.get()

            initial_data = {
                "status": status.to_dict(),
                "meta": meta.to_dict()
            }

            yield {
                "event": EventType.STATE.value,
                "id": await self._get_next_event_id(),
                "data": json.dumps(initial_data)
            }

            # Subscribe to cache updates
            cache_queue = await cache.subscribe()

            try:
                while True:
                    # Use asyncio.wait with timeout to handle both queues
                    tasks = [
                        asyncio.create_task(subscriber.queue.get()),
                        asyncio.create_task(cache_queue.get())
                    ]

                    done, pending = await asyncio.wait(
                        tasks,
                        return_when=asyncio.FIRST_COMPLETED,
                        timeout=1.0  # Check for disconnection every second
                    )

                    # Cancel pending tasks
                    for task in pending:
                        task.cancel()

                    # Process completed tasks
                    for task in done:
                        try:
                            result = task.result()

                            # Check for shutdown signal
                            if result is None:
                                return

                            # Handle SSE event
                            if isinstance(result, dict) and "event" in result:
                                yield result
                            # Handle cache update
                            elif isinstance(result, dict) and "status" in result:
                                yield {
                                    "event": EventType.STATE.value,
                                    "id": await self._get_next_event_id(),
                                    "data": json.dumps(result)
                                }

                        except asyncio.CancelledError:
                            pass
                        except Exception as e:
                            log.error(f"Error processing event: {e}")

                    # Check if client disconnected
                    if await request.is_disconnected():
                        break

            finally:
                # Unsubscribe from cache
                await cache.unsubscribe(cache_queue)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.error(f"Error in event generator: {e}")
            self.stats["total_errors"] += 1
        finally:
            # Clean up subscriber
            await self.unsubscribe(subscriber.id)

    def get_stats(self) -> dict:
        """Get SSE manager statistics."""
        return {
            **self.stats,
            "subscribers": len(self.subscribers),
            "unique_ips": len(self.subscribers_by_ip)
        }


# Global SSE manager instance
_sse_manager: Optional[SSEManager] = None
_sse_lock = asyncio.Lock()


async def get_sse_manager() -> SSEManager:
    """Get or create the global SSE manager instance."""
    global _sse_manager

    if _sse_manager is None:
        async with _sse_lock:
            if _sse_manager is None:
                _sse_manager = SSEManager(
                    max_subscribers=settings.SSE_MAX_SUBSCRIBERS_PER_IP * 20,
                    max_subscribers_per_ip=settings.SSE_MAX_SUBSCRIBERS_PER_IP,
                    heartbeat_interval=settings.SSE_HEARTBEAT_INTERVAL,
                    enable_compression=True
                )
                await _sse_manager.start()

    return _sse_manager


async def create_sse_response(request: Request) -> EventSourceResponse:
    """
    Create an SSE response for a client request.

    Args:
        request: FastAPI request object

    Returns:
        EventSourceResponse for streaming events
    """
    # Get manager
    manager = await get_sse_manager()

    # Get last event ID from headers if present
    last_event_id = request.headers.get("last-event-id")

    try:
        # Subscribe client
        subscriber = await manager.subscribe(request, last_event_id)

        # Create response
        return EventSourceResponse(
            manager.event_generator(subscriber, request),
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # Disable Nginx buffering
            }
        )

    except ValueError as e:
        # Subscription limit reached
        log.warning(f"SSE subscription rejected: {e}")
        raise
