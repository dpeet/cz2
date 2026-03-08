# tests/test_hvac_service.py
"""Tests for HVAC service layer (Phase 4 findings)."""
import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

from pycz2.core.constants import SystemMode
from pycz2.core.models import SystemStatus, ZoneStatus
from pycz2.hvac_service import HVACService


def _make_mock_client():
    """Create a mock client with a working connection() context manager."""
    mock_client = AsyncMock()

    @asynccontextmanager
    async def fake_connection():
        yield mock_client

    mock_client.connection = fake_connection
    return mock_client


@pytest.fixture
def sample_status():
    zones = [
        ZoneStatus(
            zone_id=1, temperature=72, damper_position=75,
            cool_setpoint=74, heat_setpoint=68,
            temporary=False, hold=False, out=False,
        ),
    ]
    return SystemStatus(
        system_time="Mon 02:30pm",
        system_mode=SystemMode.AUTO,
        effective_mode=SystemMode.COOL,
        fan_mode="Auto", fan_state="On", active_state="Cool On",
        all_mode=False, outside_temp=85, air_handler_temp=65,
        zone1_humidity=45,
        compressor_stage_1=False, compressor_stage_2=False,
        aux_heat_stage_1=False, aux_heat_stage_2=False,
        humidify=False, dehumidify=False, reversing_valve=False,
        raw=None, zones=zones,
    )


class TestExecuteCommandLockTimeout:
    """Finding #3: Lock timeout should be separate from command timeout."""

    @pytest.fixture
    def service(self):
        svc = HVACService()
        # Replace the lock with a fresh one for isolation
        svc._op_lock = asyncio.Lock()
        return svc

    async def test_lock_timeout_separate_from_command(self, service, sample_status):
        """When the lock is held externally, execute_command should raise
        a TimeoutError mentioning 'lock' within LOCK_TIMEOUT + margin."""
        mock_client = _make_mock_client()
        mock_client.get_status_data.return_value = sample_status
        mock_client.set_system_mode.return_value = None

        # Hold the lock externally
        await service._op_lock.acquire()

        with (
            patch("pycz2.hvac_service.get_client", return_value=mock_client),
            patch("pycz2.hvac_service.settings") as mock_settings,
        ):
            mock_settings.LOCK_TIMEOUT_SECONDS = 1
            mock_settings.COMMAND_TIMEOUT_SECONDS = 30

            with pytest.raises(TimeoutError, match="lock"):
                await service.execute_command(
                    "set_system_mode", mode=SystemMode.AUTO
                )

        service._op_lock.release()

    async def test_command_timeout_starts_after_lock(self, service):
        """Command timeout should only count time AFTER lock is acquired."""
        mock_client = _make_mock_client()

        async def slow_set(*a, **kw):
            await asyncio.sleep(999)
        mock_client.set_system_mode.side_effect = slow_set

        with (
            patch("pycz2.hvac_service.get_client", return_value=mock_client),
            patch("pycz2.hvac_service.settings") as mock_settings,
        ):
            mock_settings.LOCK_TIMEOUT_SECONDS = 10
            mock_settings.COMMAND_TIMEOUT_SECONDS = 1

            with pytest.raises(TimeoutError):
                await service.execute_command(
                    "set_system_mode", mode=SystemMode.AUTO
                )


class TestRefreshLoop:
    """Finding #18: _refresh_loop should use max(interval, backoff) not additive."""

    async def test_refresh_loop_uses_max_backoff(self):
        """_refresh_loop should sleep max(interval, backoff), not interval + backoff."""
        service = HVACService()
        service._op_lock = asyncio.Lock()
        service._stop_event = asyncio.Event()
        service._consecutive_errors = 3  # Will produce 2^3 = 8s backoff

        sleep_calls: list[float] = []
        original_sleep = asyncio.sleep

        async def track_sleep(seconds):
            sleep_calls.append(seconds)
            # Stop after first real sleep (not the initial 5s delay)
            if len(sleep_calls) >= 2:
                service._stop_event.set()
            await original_sleep(0)

        async def mock_refresh_once(source="auto"):
            # Simulate failure to keep error count up
            service._consecutive_errors = 3
            return None, None

        with (
            patch.object(service, "_refresh_once", side_effect=mock_refresh_once),
            patch("pycz2.hvac_service.asyncio.sleep", side_effect=track_sleep),
            patch("pycz2.hvac_service.settings") as mock_settings,
        ):
            mock_settings.CACHE_REFRESH_INTERVAL = 300

            await service._refresh_loop()

        # After the initial 5s delay, the loop should sleep max(300, 8) = 300
        # NOT 300 + 8 = 308 (the old additive behavior had two separate sleeps)
        # Filter out the initial 5s delay
        loop_sleeps = [s for s in sleep_calls if s != 5]
        assert len(loop_sleeps) >= 1
        # Should be a single sleep of max(interval, backoff), not two separate sleeps
        assert loop_sleeps[0] == max(300, 2**3)


class TestRefreshOnceTimeout:
    """Finding #18: _refresh_once should be bounded by COMMAND_TIMEOUT_SECONDS."""

    async def test_refresh_once_bounded_by_timeout(self):
        """_refresh_once should complete within COMMAND_TIMEOUT_SECONDS even if client stalls."""
        service = HVACService()
        service._op_lock = asyncio.Lock()

        mock_client = _make_mock_client()

        async def slow_get(**kw):
            await asyncio.sleep(999)
        mock_client.get_status_data.side_effect = slow_get

        with (
            patch("pycz2.hvac_service.get_client", return_value=mock_client),
            patch("pycz2.hvac_service.settings") as mock_settings,
        ):
            mock_settings.COMMAND_TIMEOUT_SECONDS = 1
            mock_settings.LOCK_TIMEOUT_SECONDS = 10
            mock_settings.CACHE_STALE_SECONDS = 300

            # Should complete within timeout, not hang forever
            status, meta = await asyncio.wait_for(
                service._refresh_once(source="test"),
                timeout=5,  # generous outer timeout
            )
            # Should have logged error and returned cache state
            assert service._consecutive_errors == 1
