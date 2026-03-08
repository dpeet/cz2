# tests/test_cache.py
"""Tests for StateCache — focused on subscriber notification (Finding #1)."""

import pytest

from pycz2.cache import StateCache
from pycz2.core.constants import FanMode, SystemMode
from pycz2.core.models import SystemStatus, ZoneStatus


def _make_status() -> SystemStatus:
    return SystemStatus(
        system_time="Mon 02:30pm",
        system_mode=SystemMode.AUTO,
        effective_mode=SystemMode.COOL,
        fan_mode=FanMode.AUTO,
        fan_state="On",
        active_state="Cool On",
        all_mode=False,
        outside_temp=85,
        air_handler_temp=65,
        zone1_humidity=45,
        zones=[
            ZoneStatus(
                zone_id=1, temperature=72, damper_position=75,
                cool_setpoint=74, heat_setpoint=68,
                temporary=False, hold=False, out=False,
            ),
        ],
    )


@pytest.fixture
def cache(tmp_path):
    return StateCache(db_path=tmp_path / "test_cache.db")


class TestCacheSubscriberNotification:
    """Finding #1: _notify_subscribers crashes when subscribers exist."""

    @pytest.mark.asyncio
    async def test_update_delivers_to_subscriber(self, cache):
        """Cache.update() with an active subscriber should deliver the update."""
        await cache.initialize()

        queue = await cache.subscribe()
        # Drain the initial state message
        initial = queue.get_nowait()
        assert "status" in initial

        # Now do an update — this should NOT crash
        status = _make_status()
        await cache.update(status, source="test")

        # Subscriber should receive the update
        update = queue.get_nowait()
        assert update["status"]["system_time"] == "Mon 02:30pm"
        assert "meta" in update

    @pytest.mark.asyncio
    async def test_update_without_subscribers_succeeds(self, cache):
        """Cache.update() with no subscribers should work fine."""
        await cache.initialize()
        status = _make_status()
        await cache.update(status, source="test")

        result, meta = await cache.get()
        assert result.system_time == "Mon 02:30pm"
        assert meta.source == "test"
