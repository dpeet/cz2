# src/pycz2/cache.py
"""
Thread-safe state cache for HVAC system status with persistence support.
"""
import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

import aiosqlite
from pydantic import ValidationError

from .core.models import SystemStatus
from .core.constants import SystemMode, FanMode

log = logging.getLogger(__name__)


@dataclass
class CacheMeta:
    """Metadata about the cached state."""
    connected: bool = False
    last_update_ts: float = 0
    stale_after_sec: int = 60
    source: str = "init"  # "poll", "writeback", "init", "error", "loaded"
    version: int = 0
    error: Optional[str] = None

    def is_stale(self) -> bool:
        """Check if the cache is stale based on last update time."""
        if self.last_update_ts == 0 or not self.connected:
            return True
        age = time.time() - self.last_update_ts
        return age > self.stale_after_sec

    def to_dict(self) -> dict:
        """Convert metadata to dictionary."""
        return {
            "connected": self.connected,
            "last_update_ts": self.last_update_ts,
            "stale_after_sec": self.stale_after_sec,
            "source": self.source,
            "version": self.version,
            "error": self.error,
            "is_stale": self.is_stale()
        }


class StateCache:
    """Thread-safe cache for HVAC system state with SQLite persistence."""

    def __init__(self, db_path: Optional[Path] = None, stale_after_sec: int = 60):
        self.db_path = db_path or Path.home() / ".pycz2_cache.db"
        self.stale_after_sec = stale_after_sec

        # In-memory cache
        self._status: Optional[SystemStatus] = None
        self._meta = CacheMeta(stale_after_sec=stale_after_sec)

        # Thread safety
        self._lock = asyncio.Lock()
        self._read_lock = asyncio.Lock()

        # Subscribers for real-time updates
        self._subscribers: set[asyncio.Queue] = set()

    async def initialize(self) -> None:
        """Initialize the cache and load persisted state if available."""
        async with self._lock:
            await self._init_database()
            await self._load_from_database()

    async def _init_database(self) -> None:
        """Initialize SQLite database for persistence."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS cache_state (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        status_json TEXT,
                        meta_json TEXT,
                        updated_at REAL
                    )
                """)
                await db.commit()
                log.info(f"Initialized cache database at {self.db_path}")
        except Exception as e:
            log.error(f"Failed to initialize database: {e}")

    async def _load_from_database(self) -> None:
        """Load cached state from database on startup."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT status_json, meta_json FROM cache_state WHERE id = 1"
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        status_json, meta_json = row
                        if status_json:
                            status_data = json.loads(status_json)
                            self._status = SystemStatus(**status_data)
                            log.info("Loaded cached status from database")
                        if meta_json:
                            meta_data = json.loads(meta_json)
                            self._meta = CacheMeta(**meta_data)
                            self._meta.source = "loaded"
                            log.info(f"Loaded cache metadata: version={self._meta.version}")
        except (json.JSONDecodeError, ValidationError) as e:
            log.warning(f"Invalid cached data, starting fresh: {e}")
            self._status = None
            self._meta = CacheMeta(stale_after_sec=self.stale_after_sec)
        except Exception as e:
            log.error(f"Failed to load from database: {e}")

    async def _persist_to_database(self) -> None:
        """Persist current state to database."""
        try:
            status_json = (
                json.dumps(self._status.to_dict(include_raw=True))
                if self._status
                else None
            )
            meta_json = json.dumps(asdict(self._meta))

            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO cache_state (id, status_json, meta_json, updated_at)
                    VALUES (1, ?, ?, ?)
                """, (status_json, meta_json, time.time()))
                await db.commit()
                log.debug("Persisted cache to database")
        except Exception as e:
            log.error(f"Failed to persist to database: {e}")

    def get_empty_status(self) -> SystemStatus:
        """Return a safe empty status for when no data is available."""
        return SystemStatus(
            system_time="--:--",
            system_mode=SystemMode.OFF,
            fan_mode=FanMode.AUTO,
            effective_mode=SystemMode.OFF,
            fan_state="Off",
            active_state="Idle",
            all_mode=False,
            outside_temp=0,
            air_handler_temp=0,
            zone1_humidity=0,
            compressor_stage_1=False,
            compressor_stage_2=False,
            aux_heat_stage_1=False,
            aux_heat_stage_2=False,
            humidify=False,
            dehumidify=False,
            reversing_valve=False,
            raw=None,
            zones=[],
        )

    async def get(self) -> tuple[SystemStatus, CacheMeta]:
        """
        Get cached status and metadata.
        Returns empty status if cache is not populated.
        """
        async with self._read_lock:
            status = self._status or self.get_empty_status()
            return status, self._meta

    async def update(
        self,
        status: Optional[SystemStatus],
        source: str,
        error: Optional[str] = None
    ) -> None:
        """
        Update cache with new status and notify subscribers.

        Args:
            status: The new system status (None if error)
            source: Source of the update ("poll", "writeback", "error")
            error: Error message if update failed
        """
        async with self._lock:
            # Update version for optimistic locking
            self._meta.version += 1

            # Update status if provided
            if status is not None:
                self._status = status
                self._meta.connected = True
                self._meta.error = None
            else:
                self._meta.connected = False
                self._meta.error = error

            # Update metadata
            self._meta.last_update_ts = time.time()
            self._meta.source = source

            # Persist to database
            await self._persist_to_database()

            # Notify subscribers
            await self._notify_subscribers()

            log.info(
                f"Cache updated: version={self._meta.version}, "
                f"source={source}, connected={self._meta.connected}"
            )

    async def update_partial(
        self,
        updates: dict[str, Any],
        source: str
    ) -> None:
        """
        Apply partial updates to cached status.
        Useful for optimistic updates after commands.
        """
        async with self._lock:
            if self._status is None:
                log.warning("Cannot apply partial update to empty cache")
                return

            # Create a copy and apply updates
            status_dict = self._status.to_dict(include_raw=True)
            status_dict.update(updates)

            try:
                self._status = SystemStatus(**status_dict)
                self._meta.version += 1
                self._meta.last_update_ts = time.time()
                self._meta.source = source

                await self._persist_to_database()
                await self._notify_subscribers()

                log.debug(f"Applied partial update: {updates}")
            except ValidationError as e:
                log.error(f"Invalid partial update: {e}")

    async def check_version(self, expected_version: int) -> bool:
        """
        Check if the cache version matches expected version.
        Used for optimistic locking.
        """
        async with self._read_lock:
            return self._meta.version == expected_version

    async def subscribe(self) -> asyncio.Queue:
        """
        Subscribe to cache updates.
        Returns a queue that will receive updates.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=10)
        self._subscribers.add(queue)

        # Send initial state
        status, meta = await self.get()
        try:
            queue.put_nowait({
                "status": status.to_dict(),
                "meta": meta.to_dict()
            })
        except asyncio.QueueFull:
            log.warning("Subscriber queue full, skipping initial state")

        return queue

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Unsubscribe from cache updates."""
        self._subscribers.discard(queue)

    async def _notify_subscribers(self) -> None:
        """Notify all subscribers of cache update."""
        if not self._subscribers:
            return

            status = self._status or self.get_empty_status()
        update = {
            "status": status.to_dict(),
            "meta": self._meta.to_dict()
        }

        # Notify all subscribers, removing dead ones
        dead_subscribers = []
        for queue in self._subscribers:
            try:
                queue.put_nowait(update)
            except asyncio.QueueFull:
                # Skip if queue is full (slow consumer)
                log.debug("Subscriber queue full, skipping update")
            except Exception as e:
                log.warning(f"Failed to notify subscriber: {e}")
                dead_subscribers.append(queue)

        # Clean up dead subscribers
        for queue in dead_subscribers:
            self._subscribers.discard(queue)

    async def set_connection_status(
        self,
        connected: bool,
        source: str,
        error: Optional[str] = None
    ) -> None:
        """
        Update only the connection status without modifying cached data.

        This is used when the worker connects/disconnects but hasn't
        polled for data yet. Keeps is_stale true if no recent data.

        Args:
            connected: Whether the HVAC connection is established
            source: Source of the update ("connect", "disconnect", "error")
            error: Optional error message if connection failed
        """
        async with self._lock:
            self._meta.connected = connected
            self._meta.source = source
            self._meta.error = error
            self._meta.version += 1

            # Don't update last_update_ts - that's for actual data updates
            # This keeps is_stale() returning true until we get real data

            # Persist and notify
            await self._persist_to_database()
            await self._notify_subscribers()

            log.info(
                f"Connection status updated: connected={connected}, "
                f"source={source}, error={error}"
            )

    async def clear(self) -> None:
        """Clear the cache and reset to initial state."""
        async with self._lock:
            self._status = None
            self._meta = CacheMeta(stale_after_sec=self.stale_after_sec)
            await self._persist_to_database()
            await self._notify_subscribers()
            log.info("Cache cleared")

    async def get_stats(self) -> dict:
        """Get cache statistics for monitoring."""
        async with self._read_lock:
            return {
                "has_data": self._status is not None,
                "version": self._meta.version,
                "connected": self._meta.connected,
                "is_stale": self._meta.is_stale(),
                "last_update_ts": self._meta.last_update_ts,
                "age_seconds": time.time() - self._meta.last_update_ts if self._meta.last_update_ts > 0 else None,
                "source": self._meta.source,
                "subscriber_count": len(self._subscribers),
                "error": self._meta.error
            }


# Global cache instance
_cache: Optional[StateCache] = None
_cache_lock = asyncio.Lock()


async def get_cache() -> StateCache:
    """Get or create the global cache instance."""
    global _cache

    if _cache is None:
        async with _cache_lock:
            if _cache is None:
                from .config import settings
                # Use configured path or default
                db_path = Path(settings.CACHE_DB_PATH) if settings.CACHE_DB_PATH else Path.home() / ".pycz2_cache.db"
                _cache = StateCache(
                    db_path=db_path,
                    stale_after_sec=settings.CACHE_STALE_SECONDS
                )
                await _cache.initialize()

    return _cache
