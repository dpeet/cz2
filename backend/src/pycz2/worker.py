# src/pycz2/worker.py
"""
Background worker for managing HVAC connection and command processing.
"""
import asyncio
import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from fastapi import HTTPException

from .cache import get_cache
from .config import settings
from .core.client import ComfortZoneIIClient
from .core.constants import FanMode, SystemMode
from .core.models import SystemStatus

log = logging.getLogger(__name__)


class CommandType(Enum):
    """Types of commands the worker can process."""
    POLL_STATUS = "poll_status"
    SET_SYSTEM_MODE = "set_system_mode"
    SET_FAN_MODE = "set_fan_mode"
    SET_ZONE_TEMPERATURE = "set_zone_temperature"
    SET_ZONE_HOLD = "set_zone_hold"


class ConnectionState(Enum):
    """Connection states for the worker."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    SHUTDOWN = "shutdown"


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failures detected, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class HVACCommand:
    """Command to be processed by the worker."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: CommandType = CommandType.POLL_STATUS
    args: dict[str, Any] = field(default_factory=dict)
    future: asyncio.Future = field(default_factory=asyncio.Future)
    timestamp: float = field(default_factory=time.time)
    priority: int = 0  # 0=normal, 1=high
    retry_count: int = 0
    max_retries: int = 3

    def __lt__(self, other):
        """Priority queue comparison (higher priority first)."""
        if self.priority != other.priority:
            return self.priority > other.priority
        return self.timestamp < other.timestamp


@dataclass
class CommandStatus:
    """Status tracking for submitted commands."""
    id: str
    type: CommandType
    args: dict
    status: str  # queued|processing|complete|failed
    created_at: float
    completed_at: Optional[float] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    cache_version: int = 0


class CommandTracker:
    """Tracks command execution status and history."""

    def __init__(self, max_age: int = 300):
        """
        Initialize command tracker.

        Args:
            max_age: Maximum age in seconds before commands are cleaned up
        """
        self._commands: dict[str, CommandStatus] = {}
        self._lock = asyncio.Lock()
        self._max_age = max_age

    async def add(
        self,
        command_type: CommandType,
        args: dict,
        cache_version: int = 0
    ) -> CommandStatus:
        """Add a new command to tracking."""
        async with self._lock:
            cmd = CommandStatus(
                id=str(uuid.uuid4()),
                type=command_type,
                args=args,
                status="queued",
                created_at=time.time(),
                cache_version=cache_version
            )
            self._commands[cmd.id] = cmd
            self._cleanup_old()
            return cmd

    async def update(self, command_id: str, **kwargs) -> None:
        """Update command status."""
        async with self._lock:
            if command_id in self._commands:
                for key, value in kwargs.items():
                    if hasattr(self._commands[command_id], key):
                        setattr(self._commands[command_id], key, value)

    async def get(self, command_id: str) -> Optional[CommandStatus]:
        """Get command status by ID."""
        async with self._lock:
            return self._commands.get(command_id)

    async def get_all(self) -> list[CommandStatus]:
        """Get all tracked commands."""
        async with self._lock:
            self._cleanup_old()
            return list(self._commands.values())

    def _cleanup_old(self) -> None:
        """Remove expired commands."""
        now = time.time()
        expired = [
            cmd_id for cmd_id, cmd in self._commands.items()
            if now - cmd.created_at > self._max_age
        ]
        for cmd_id in expired:
            del self._commands[cmd_id]


def calculate_provisional_state(
    current: Optional[SystemStatus],
    command_type: CommandType,
    args: dict
) -> dict:
    """
    Calculate optimistic state change based on command.

    Args:
        current: Current system status
        command_type: Type of command being executed
        args: Command arguments

    Returns:
        Dictionary with provisional state changes
    """
    if not current:
        return {}

    provisional = current.to_dict()

    if command_type == CommandType.SET_ZONE_TEMPERATURE:
        zone_idx = args.get("zones", [1])[0] - 1
        if 0 <= zone_idx < len(provisional["zones"]):
            zone = provisional["zones"][zone_idx]
            if args.get("heat_setpoint") is not None:
                zone["heat_setpoint"] = args["heat_setpoint"]
            if args.get("cool_setpoint") is not None:
                zone["cool_setpoint"] = args["cool_setpoint"]
            if "hold" in args:
                zone["hold"] = bool(args["hold"])
            if "temporary_hold" in args:
                zone["temporary"] = bool(args["temporary_hold"])

    elif command_type == CommandType.SET_SYSTEM_MODE:
        mode = args.get("mode")
        if isinstance(mode, SystemMode):
            provisional["system_mode"] = mode.value
        elif isinstance(mode, str):
            provisional["system_mode"] = mode
        if "all_zones_mode" in args:
            provisional["all_mode"] = bool(args["all_zones_mode"])

    elif command_type == CommandType.SET_FAN_MODE:
        mode = args.get("mode")
        if isinstance(mode, FanMode):
            provisional["fan_mode"] = mode.value
        elif isinstance(mode, str):
            provisional["fan_mode"] = mode

    elif command_type == CommandType.SET_ZONE_HOLD:
        zone_idx = args.get("zones", [1])[0] - 1
        if 0 <= zone_idx < len(provisional["zones"]):
            zone = provisional["zones"][zone_idx]
            if "hold" in args:
                zone["hold"] = bool(args["hold"])
            if "temporary_hold" in args:
                zone["temporary"] = bool(args["temporary_hold"])

    return provisional


class CircuitBreaker:
    """Circuit breaker for handling connection failures."""

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        half_open_max_calls: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.half_open_max_calls = half_open_max_calls
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = CircuitBreakerState.CLOSED
        self.half_open_calls = 0

    def call(self):
        """Check if a call is allowed."""
        if self.state == CircuitBreakerState.CLOSED:
            return True

        if self.state == CircuitBreakerState.OPEN:
            if time.time() - self.last_failure_time > self.timeout:
                self.state = CircuitBreakerState.HALF_OPEN
                self.half_open_calls = 0
                log.info("Circuit breaker entering half-open state")
            else:
                return False

        if self.state == CircuitBreakerState.HALF_OPEN:
            if self.half_open_calls >= self.half_open_max_calls:
                return False
            self.half_open_calls += 1
            return True

        return False

    def success(self):
        """Record a successful call."""
        if self.state == CircuitBreakerState.HALF_OPEN:
            if self.half_open_calls >= self.half_open_max_calls:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                log.info("Circuit breaker closed (recovered)")
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = 0

    def failure(self):
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            log.warning("Circuit breaker reopened due to failure in half-open state")
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            log.error(
                f"Circuit breaker opened after {self.failure_count} failures"
            )


class HVACWorker:
    """Background worker for HVAC operations."""

    def __init__(self, client: ComfortZoneIIClient):
        self.client = client
        self.connection_state = ConnectionState.DISCONNECTED
        self.command_queue: asyncio.PriorityQueue = asyncio.PriorityQueue(
            maxsize=settings.COMMAND_QUEUE_MAX_SIZE
        )
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            timeout=60.0
        )

        # Connection management
        self._connection_lock = asyncio.Lock()
        self._connected = False
        self._last_heartbeat = 0
        self._reconnect_attempts = 0

        # Polling state
        self._last_poll_time = 0
        self._poll_in_progress = False
        self._poll_waiters: list[asyncio.Future] = []

        # Dead letter queue for failed commands
        self._dead_letter_queue: list[HVACCommand] = []

        # Command tracking
        self.tracker = CommandTracker(max_age=settings.COMMAND_TIMEOUT_SECONDS * 10)

        # Shutdown flag
        self._shutdown = False

        # Statistics
        self.stats = {
            "commands_processed": 0,
            "commands_failed": 0,
            "polls_completed": 0,
            "connection_failures": 0,
            "reconnections": 0,
        }

    async def start(self):
        """Start the worker tasks."""
        log.info("Starting HVAC worker")
        self.connection_state = ConnectionState.DISCONNECTED

        # Start background tasks
        tasks = [
            asyncio.create_task(self._connection_manager()),
            asyncio.create_task(self._command_processor()),
            asyncio.create_task(self._polling_task()),
        ]

        # Wait for all tasks (they should run forever unless stopped)
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            log.info("Worker tasks cancelled")
            raise

    async def stop(self):
        """Stop the worker gracefully."""
        log.info("Stopping HVAC worker")
        self._shutdown = True
        self.connection_state = ConnectionState.SHUTDOWN

        # Close connection if open
        async with self._connection_lock:
            if self._connected:
                await self.client.close()
                self._connected = False

        # Cancel pending commands
        while not self.command_queue.empty():
            try:
                _, cmd = self.command_queue.get_nowait()
                cmd.future.cancel()
            except asyncio.QueueEmpty:
                break

        log.info("HVAC worker stopped")

    async def _connection_manager(self):
        """Manage the HVAC connection lifecycle."""
        while not self._shutdown:
            try:
                if not self._connected:
                    await self._connect_with_backoff()

                # Heartbeat to keep connection alive
                if self._connected:
                    await self._heartbeat()

                await asyncio.sleep(10)  # Check connection every 10 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Connection manager error: {e}")
                self.stats["connection_failures"] += 1
                await asyncio.sleep(5)

    async def _connect_with_backoff(self):
        """Connect to HVAC with exponential backoff."""
        if not self.circuit_breaker.call():
            log.debug("Circuit breaker is open, skipping connection attempt")
            return

        self.connection_state = ConnectionState.CONNECTING
        base_delay = settings.WORKER_RECONNECT_DELAY
        max_delay = settings.WORKER_MAX_RECONNECT_DELAY

        try:
            async with self._connection_lock:
                log.info(f"Attempting to connect to HVAC (attempt {self._reconnect_attempts + 1})")
                await self.client.connect()
                self._connected = True
                self.connection_state = ConnectionState.CONNECTED
                self._reconnect_attempts = 0
                self.circuit_breaker.success()
                self.stats["reconnections"] += 1
                log.info("Successfully connected to HVAC")

                # Update cache with connection status
                cache = await get_cache()
                await cache.set_connection_status(connected=True, source="connect")

        except Exception as e:
            self._reconnect_attempts += 1
            self.circuit_breaker.failure()
            self.connection_state = ConnectionState.ERROR
            log.error(f"Failed to connect: {e}")

            # Update cache with error
            cache = await get_cache()
            await cache.set_connection_status(connected=False, source="error", error=str(e))

            # Calculate backoff with jitter
            delay = min(
                base_delay * (2 ** self._reconnect_attempts) + random.uniform(0, 1),
                max_delay
            )
            log.info(f"Retrying connection in {delay:.1f} seconds")
            await asyncio.sleep(delay)

    async def _heartbeat(self):
        """Send heartbeat to check connection health."""
        if time.time() - self._last_heartbeat < 60:  # Heartbeat every 60 seconds
            return

        async with self._connection_lock:
            if not self._connected or not self.client.is_connected():
                self._connected = False
                self.connection_state = ConnectionState.DISCONNECTED
                return

            try:
                # Try a simple read operation as heartbeat
                # This is a no-op that verifies the connection is alive
                self._last_heartbeat = time.time()
                log.debug("Heartbeat successful")
            except Exception as e:
                log.warning(f"Heartbeat failed: {e}")
                self._connected = False
                self.connection_state = ConnectionState.DISCONNECTED
                await self.client.close()

    async def _command_processor(self):
        """Process commands from the queue."""
        while not self._shutdown:
            try:
                # Wait for command with timeout
                try:
                    priority, command = await asyncio.wait_for(
                        self.command_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # Check if we can process
                if not self._connected:
                    log.warning("Not connected, requeueing command")
                    if command.retry_count < command.max_retries:
                        command.retry_count += 1
                        await self.command_queue.put((priority, command))
                    else:
                        command.future.set_exception(
                            ConnectionError("HVAC not connected")
                        )
                        self._dead_letter_queue.append(command)
                    continue

                # Update tracker status
                await self.tracker.update(command.id, status="processing")

                # Process the command
                try:
                    result = await self._execute_command(command)
                    self.stats["commands_processed"] += 1

                    # Update tracker with success
                    await self.tracker.update(
                        command.id,
                        status="complete",
                        completed_at=time.time(),
                        result=result.to_dict() if result else None
                    )

                    # Broadcast success via SSE
                    from .sse import EventType, get_sse_manager
                    sse = await get_sse_manager()
                    await sse.broadcast_event(
                        EventType.COMMAND_RESULT,
                        {
                            "command_id": command.id,
                            "status": "complete",
                            "type": command.type.value,
                            "result": result.to_dict() if result else None
                        }
                    )

                    # Set future for backward compatibility (will remove later)
                    if not command.future.done():
                        command.future.set_result(result)

                    # Poll after write operations
                    if command.type != CommandType.POLL_STATUS:
                        await self._trigger_poll()

                except Exception as e:
                    log.error(f"Command execution failed: {e}")
                    self.stats["commands_failed"] += 1

                    if command.retry_count < command.max_retries:
                        command.retry_count += 1
                        await self.command_queue.put((priority, command))
                    else:
                        # Update tracker with failure
                        await self.tracker.update(
                            command.id,
                            status="failed",
                            completed_at=time.time(),
                            error=str(e)
                        )

                        # Broadcast failure via SSE
                        from .sse import EventType, get_sse_manager
                        sse = await get_sse_manager()
                        await sse.broadcast_event(
                            EventType.COMMAND_RESULT,
                            {
                                "command_id": command.id,
                                "status": "failed",
                                "type": command.type.value,
                                "error": str(e)
                            }
                        )

                        # Set future for backward compatibility
                        if not command.future.done():
                            command.future.set_exception(e)
                        self._dead_letter_queue.append(command)

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Command processor error: {e}")
                await asyncio.sleep(1)

    async def _execute_command(self, command: HVACCommand) -> Any:
        """Execute a single command."""
        async with self._connection_lock:
            if not self._connected:
                raise ConnectionError("Not connected to HVAC")

            log.debug(f"Executing command: {command.type} with args {command.args}")

            try:
                if command.type == CommandType.POLL_STATUS:
                    return await self.client.get_status_data()

                elif command.type == CommandType.SET_SYSTEM_MODE:
                    await self.client.set_system_mode(**command.args)
                    return await self.client.get_status_data()

                elif command.type == CommandType.SET_FAN_MODE:
                    await self.client.set_fan_mode(**command.args)
                    return await self.client.get_status_data()

                elif command.type == CommandType.SET_ZONE_TEMPERATURE:
                    await self.client.set_zone_setpoints(**command.args)
                    return await self.client.get_status_data()

                elif command.type == CommandType.SET_ZONE_HOLD:
                    await self.client.set_zone_setpoints(**command.args)
                    return await self.client.get_status_data()

                else:
                    raise ValueError(f"Unknown command type: {command.type}")

            except Exception as e:
                log.error(f"Command execution error: {e}")
                # Check if connection was lost
                if not self.client.is_connected():
                    self._connected = False
                    self.connection_state = ConnectionState.DISCONNECTED
                raise

    async def _polling_task(self):
        """Periodic polling task."""
        while not self._shutdown:
            try:
                # Wait for poll interval
                await asyncio.sleep(settings.WORKER_POLL_INTERVAL)

                if self._connected:
                    await self._trigger_poll()

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Polling task error: {e}")

    async def _trigger_poll(self):
        """Trigger a status poll."""
        if self._poll_in_progress:
            log.debug("Poll already in progress, skipping")
            return

        if time.time() - self._last_poll_time < 5:  # Min 5 seconds between polls
            log.debug("Recent poll exists, skipping")
            return

        self._poll_in_progress = True
        try:
            # Create poll command
            command = HVACCommand(
                type=CommandType.POLL_STATUS,
                priority=0  # Normal priority
            )

            # Add to queue
            await self.command_queue.put((command.priority, command))

            # Wait for result
            try:
                status = await asyncio.wait_for(
                    command.future,
                    timeout=settings.COMMAND_TIMEOUT_SECONDS
                )

                # Update cache
                cache = await get_cache()
                await cache.update(status, source="poll")

                self._last_poll_time = time.time()
                self.stats["polls_completed"] += 1
                log.debug("Poll completed successfully")

                # Notify any waiters
                for waiter in self._poll_waiters:
                    if not waiter.done():
                        waiter.set_result(status)
                self._poll_waiters.clear()

            except asyncio.TimeoutError:
                log.error("Poll timed out")

        finally:
            self._poll_in_progress = False

    async def enqueue_command(
        self,
        command_type: CommandType,
        args: dict[str, Any],
        priority: int = 0
    ) -> CommandStatus:
        """
        Queue command and return immediately with tracking info.

        Returns:
            CommandStatus with command ID for tracking
        """
        if self.command_queue.full():
            raise HTTPException(429, "Command queue full, try again later")

        # Get current cache version for conflict detection
        cache = await get_cache()
        _, meta = await cache.get()

        # Create tracked command
        cmd_status = await self.tracker.add(command_type, args, meta.version)

        # Create internal command object with tracker's ID
        command = HVACCommand(
            id=cmd_status.id,  # Use tracker's ID
            type=command_type,
            args=args,
            priority=priority
        )

        # Queue for processing (non-blocking)
        await self.command_queue.put((command.priority, command))

        # Return status immediately
        return cmd_status

    async def wait_for_poll(self) -> SystemStatus:
        """Wait for the next poll result."""
        if self._last_poll_time > 0 and time.time() - self._last_poll_time < 5:
            # Recent data exists, get from cache
            cache = await get_cache()
            status, _ = await cache.get()
            return status

        # Wait for next poll
        waiter: asyncio.Future = asyncio.Future()
        self._poll_waiters.append(waiter)
        await self._trigger_poll()

        try:
            return await asyncio.wait_for(waiter, timeout=30)
        except asyncio.TimeoutError:
            self._poll_waiters.remove(waiter)
            raise

    def get_stats(self) -> dict:
        """Get worker statistics."""
        return {
            **self.stats,
            "connection_state": self.connection_state.value,
            "circuit_breaker_state": self.circuit_breaker.state.value,
            "queue_size": self.command_queue.qsize(),
            "dead_letter_count": len(self._dead_letter_queue),
            "connected": self._connected,
            "last_poll_time": self._last_poll_time,
            "reconnect_attempts": self._reconnect_attempts,
        }


# Global worker instance
_worker: Optional[HVACWorker] = None
_worker_lock = asyncio.Lock()


async def get_worker() -> HVACWorker:
    """Get or create the global worker instance."""
    global _worker

    if _worker is None:
        async with _worker_lock:
            if _worker is None:
                from .core.client import ComfortZoneIIClient
                client = ComfortZoneIIClient(
                    connect_str=settings.CZ_CONNECT,
                    zone_count=settings.CZ_ZONES,
                    device_id=settings.CZ_ID
                )
                _worker = HVACWorker(client)

    return _worker
