# tests/test_api.py
import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from tenacity import RetryError

from pycz2.api import app
from pycz2.core.client import ComfortZoneIIClient, get_client, get_lock
from pycz2.core.constants import FanMode, SystemMode
from pycz2.core.models import SystemStatus, ZoneStatus
from pycz2.mqtt import MqttClient, get_mqtt_client


class TestAPIIntegration:
    """Integration tests for the FastAPI application."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock ComfortZoneIIClient."""
        client = AsyncMock(spec=ComfortZoneIIClient)
        connection_cm = AsyncMock()
        connection_cm.__aenter__.return_value = None
        connection_cm.__aexit__.return_value = None
        client.connection.return_value = connection_cm
        return client

    @pytest.fixture
    def mock_mqtt_client(self):
        """Create a mock MqttClient."""
        mqtt_client = AsyncMock(spec=MqttClient)
        return mqtt_client

    @pytest.fixture
    def mock_lock(self):
        """Create a real asyncio.Lock for testing."""
        return asyncio.Lock()

    @pytest.fixture
    def test_app(self, mock_client, mock_mqtt_client, mock_lock):
        """Create a FastAPI test app with mocked dependencies."""
        # Override dependencies
        app.dependency_overrides[get_client] = lambda: mock_client
        app.dependency_overrides[get_mqtt_client] = lambda: mock_mqtt_client
        app.dependency_overrides[get_lock] = lambda: mock_lock

        async def noop(*args, **kwargs):
            return None

        hvac_client_patch = patch("pycz2.hvac_service.get_client", lambda: mock_client)
        hvac_start_patch = patch("pycz2.hvac_service.HVACService.start", noop)
        hvac_stop_patch = patch("pycz2.hvac_service.HVACService.stop", noop)

        # Disable worker mode for tests (use synchronous mode)
        with (
            patch("pycz2.api.settings.WORKER_ENABLED", False),
            hvac_client_patch,
            hvac_start_patch,
            hvac_stop_patch,
        ):
            yield app

        # Clean up overrides after test
        app.dependency_overrides.clear()

    @pytest.fixture
    def client(self, test_app):
        """Create a TestClient for the FastAPI app."""
        with TestClient(test_app) as test_client:
            yield test_client

    @pytest.fixture
    def sample_status(self):
        """Create a sample SystemStatus object for testing."""
        zones = [
            ZoneStatus(
                zone_id=1,
                temperature=72,
                damper_position=75,
                cool_setpoint=74,
                heat_setpoint=68,
                temporary=False,
                hold=False,
                out=False,
            ),
            ZoneStatus(
                zone_id=2,
                temperature=70,
                damper_position=50,
                cool_setpoint=74,
                heat_setpoint=68,
                temporary=False,
                hold=False,
                out=False,
            ),
        ]

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
            compressor_stage_1=False,
            compressor_stage_2=False,
            aux_heat_stage_1=False,
            aux_heat_stage_2=False,
            humidify=False,
            dehumidify=False,
            reversing_valve=False,
            raw=None,
            zones=zones,
        )

    def test_get_status_success(self, client, mock_client, sample_status):
        """Test successful GET /status request with new structured format."""
        # With cache enabled, we need to populate it first
        # Call /update to populate cache with sample data
        mock_client.get_status_data.return_value = sample_status

        # First do an update to populate cache
        response = client.post("/update")
        assert response.status_code == 200

        # Now test the GET /status which returns from cache
        response = client.get("/status")

        # Verify response
        assert response.status_code == 200
        data = response.json()

        # With cache enabled, we get structured response
        assert "status" in data
        assert "meta" in data

        # Verify meta fields
        meta = data["meta"]
        assert "connected" in meta
        assert "is_stale" in meta
        assert "source" in meta

        # Verify status data
        status = data["status"]
        assert status["system_time"] == "Mon 02:30pm"
        assert status["system_mode"] == "Auto"
        assert status["effective_mode"] == "Cool"
        assert status["fan_mode"] == "Auto"
        assert status["fan_state"] == "On"
        assert status["active_state"] == "Cool On"
        assert status["all_mode"] is False
        assert status["outside_temp"] == 85
        assert status["air_handler_temp"] == 65
        assert status["zone1_humidity"] == 45
        assert status["compressor_stage_1"] is False
        assert status["compressor_stage_2"] is False
        assert status["aux_heat_stage_1"] is False
        assert status["aux_heat_stage_2"] is False
        assert status["humidify"] is False
        assert status["dehumidify"] is False
        assert status["reversing_valve"] is False
        assert "raw" not in status
        assert len(status["zones"]) == 2

        # Verify zone data
        zone1 = status["zones"][0]
        assert zone1["zone_id"] == 1
        assert zone1["temperature"] == 72
        assert zone1["cool_setpoint"] == 74
        assert zone1["heat_setpoint"] == 68

    def test_get_status_success_flat_format(self, client, mock_client, sample_status):
        """Test successful GET /status request with flat=1 parameter for legacy compatibility."""
        # Configure mock to return sample status
        mock_client.get_status_data.return_value = sample_status

        # Make request with flat=1 parameter
        response = client.get("/status?flat=1")

        # Verify response
        assert response.status_code == 200
        data = response.json()

        # With flat=1, we get legacy flat format
        assert "system_time" in data
        assert "status" not in data  # No nested structure
        assert "meta" not in data

        # Verify basic structure and values (flat format)
        assert data["system_time"] == "Mon 02:30pm"
        assert data["system_mode"] == "Auto"
        assert data["effective_mode"] == "Cool"
        assert data["fan_mode"] == "Auto"
        assert data["fan_state"] == "On"
        assert data["active_state"] == "Cool On"
        # flat=1 converts all_mode boolean to numeric (0/1)
        assert data["all_mode"] == 0  # False becomes 0
        assert data["outside_temp"] == 85
        assert data["air_handler_temp"] == 65
        assert data["zone1_humidity"] == 45
        assert data["compressor_stage_1"] is False
        assert data["compressor_stage_2"] is False
        assert data["aux_heat_stage_1"] is False
        assert data["aux_heat_stage_2"] is False
        assert data["humidify"] is False
        assert data["dehumidify"] is False
        assert data["reversing_valve"] is False
        assert "raw" not in data
        assert len(data["zones"]) == 2

        # Verify flat format includes time field
        assert "time" in data
        assert isinstance(data["time"], int)

        # Verify zone data
        zone1 = data["zones"][0]
        assert zone1["zone_id"] == 1
        assert zone1["temperature"] == 72
        assert zone1["cool_setpoint"] == 74
        assert zone1["heat_setpoint"] == 68
        # flat=1 converts damper_position to string
        assert isinstance(zone1["damper_position"], str)

    def test_get_status_with_raw(self, client, mock_client, sample_status):
        """Test GET /status returns raw blob when requested."""
        raw_blob = "QUJD"
        mock_status = sample_status.model_copy(update={"raw": raw_blob})
        mock_client.get_status_data.return_value = mock_status

        response = client.get("/status?raw=1")

        assert response.status_code == 200
        data = response.json()
        status = data["status"]
        assert status["raw"] == raw_blob
        mock_client.get_status_data.assert_called_with(include_raw=True)

    def test_get_status_with_cache_returns_empty(self, client, mock_client):
        """Test GET /status with cache enabled returns empty status when no data cached."""
        # Clear the cache first to ensure we start with empty state
        response = client.post("/cache/clear")
        assert response.status_code == 200

        # With cache enabled and no data, we get empty status
        response = client.get("/status")

        # Should succeed even without HVAC connection
        assert response.status_code == 200
        data = response.json()

        # Check we have structured response
        assert "status" in data
        assert "meta" in data

        # Meta should indicate disconnected/stale
        meta = data["meta"]
        assert meta["connected"] is False
        assert meta["is_stale"] is True

        # Status should be empty/default values
        status = data["status"]
        assert status["system_time"] == "--:--"
        assert status["system_mode"] == "Off"
        assert status["zones"] == []

    def test_post_update_success(
        self, client, mock_client, mock_mqtt_client, sample_status
    ):
        """Test successful POST /update request."""
        # Configure mocks
        mock_client.get_status_data.return_value = sample_status
        mock_mqtt_client.publish_status.return_value = None

        # Make request
        response = client.post("/update")

        # Verify response - with cache enabled, returns structured format
        assert response.status_code == 200
        data = response.json()

        # Should have status and meta
        assert "status" in data
        assert "meta" in data
        assert data["status"]["system_mode"] == "Auto"

        # Verify mocks were called
        mock_client.get_status_data.assert_called_once()

    def test_post_system_mode_success(
        self, client, mock_client, mock_mqtt_client, sample_status
    ):
        """Test successful POST /system/mode request."""
        # Configure mocks
        mock_client.set_system_mode.return_value = None
        mock_client.get_status_data.return_value = sample_status
        mock_mqtt_client.publish_status.return_value = None

        # Request payload
        payload = {"mode": "Heat", "all": True}

        # Make request
        response = client.post("/system/mode", json=payload)

        # Verify response - with cache enabled, returns structured format
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "meta" in data
        assert data["status"]["system_mode"] == "Auto"  # From sample_status

        # Verify mock was called with correct arguments
        mock_client.set_system_mode.assert_called_once_with(
            mode=SystemMode.HEAT, all_zones_mode=True
        )
        mock_client.get_status_data.assert_called_once()

    def test_post_system_mode_invalid_data(self, client):
        """Test POST /system/mode with invalid data."""
        # Invalid mode
        payload = {"mode": "InvalidMode"}

        # Make request
        response = client.post("/system/mode", json=payload)

        # Verify error response
        assert response.status_code == 422  # Validation error

    def test_post_system_fan_success(
        self, client, mock_client, mock_mqtt_client, sample_status
    ):
        """Test successful POST /system/fan request."""
        # Configure mocks
        mock_client.set_fan_mode.return_value = None
        mock_client.get_status_data.return_value = sample_status
        mock_mqtt_client.publish_status.return_value = None

        # Request payload
        payload = {"fan": "On"}

        # Make request
        response = client.post("/system/fan", json=payload)

        # Verify response - with cache enabled, returns structured format
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "meta" in data
        assert data["status"]["fan_mode"] == "Auto"  # From sample_status

        # Verify mock was called with correct arguments
        mock_client.set_fan_mode.assert_called_once_with(FanMode.ON)
        mock_client.get_status_data.assert_called_once()

    @patch("pycz2.api.settings.CZ_ZONES", 4)  # Mock 4 zones for this test
    def test_post_zone_temperature_success(
        self, client, mock_client, mock_mqtt_client, sample_status
    ):
        """Test successful POST /zones/{zone_id}/temperature request."""
        # Configure mocks
        mock_client.set_zone_setpoints.return_value = None
        mock_client.get_status_data.return_value = sample_status
        mock_mqtt_client.publish_status.return_value = None

        # Request payload
        payload = {"heat": 70, "cool": 76, "temp": True, "hold": False, "out": False}

        # Make request
        response = client.post("/zones/2/temperature", json=payload)

        # Verify response - with cache enabled, returns structured format
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "meta" in data
        assert data["status"]["system_mode"] == "Auto"

        # Verify mock was called with correct arguments
        mock_client.set_zone_setpoints.assert_called_once_with(
            zones=[2],
            heat_setpoint=70,
            cool_setpoint=76,
            temporary_hold=True,
            hold=False,
            out_mode=False,
        )
        mock_client.get_status_data.assert_called_once()

    @patch("pycz2.api.settings.CZ_ZONES", 4)  # Mock 4 zones for this test
    def test_post_zone_temperature_invalid_zone(self, client):
        """Test POST /zones/{zone_id}/temperature with invalid zone ID."""
        # Request payload
        payload = {"heat": 70, "cool": 76}

        # Make request with invalid zone (zone 99 when only 4 zones exist)
        response = client.post("/zones/99/temperature", json=payload)

        # Verify error response
        assert response.status_code == 404
        data = response.json()
        assert "Zone 99 not found" in data["detail"]

    def test_post_zone_temperature_invalid_setpoint(self, client):
        """Test POST /zones/{zone_id}/temperature with invalid temperature values."""
        # Invalid heat setpoint (too low)
        payload = {
            "heat": 30,  # Below minimum of 45
            "cool": 76,
        }

        # Make request
        response = client.post("/zones/1/temperature", json=payload)

        # Verify validation error
        assert response.status_code == 422

    def test_post_zone_temperature_heat_too_close_to_cool_model_validation(
        self, client
    ):
        """Test model-level validation when heat and cool are both provided with insufficient gap."""
        # Heat and cool with only 1°F gap (requires 2°F)
        payload = {
            "heat": 71,
            "cool": 72,  # Only 1°F gap
            "temp": True,
        }

        # Make request
        response = client.post("/zones/1/temperature", json=payload)

        # Verify validation error
        assert response.status_code == 422
        data = response.json()
        assert "must be at least 2°F below" in str(data)

    def test_post_zone_temperature_heat_conflicts_with_existing_cool(
        self, client, mock_client, sample_status
    ):
        """Test API-level validation when heat conflicts with existing cool setpoint."""
        # Configure mocks - zone has cool setpoint of 74
        mock_client.get_status_data.return_value = sample_status

        # Try to set heat to 73 (only 1°F gap from cool=74)
        payload = {
            "heat": 73,  # Too close to existing cool=74
            "temp": True,
        }

        # Make request
        response = client.post("/zones/1/temperature", json=payload)

        # Verify validation error
        assert response.status_code == 422
        data = response.json()
        assert "must be at least 2°F below" in data["detail"]
        assert "74" in data["detail"]  # Should mention current cool setpoint

    def test_post_zone_temperature_cool_conflicts_with_existing_heat(
        self, client, mock_client, sample_status
    ):
        """Test API-level validation when cool conflicts with existing heat setpoint."""
        # Configure mocks - zone has heat setpoint of 68
        mock_client.get_status_data.return_value = sample_status

        # Try to set cool to 69 (only 1°F gap from heat=68)
        payload = {
            "cool": 69,  # Too close to existing heat=68
            "temp": True,
        }

        # Make request
        response = client.post("/zones/1/temperature", json=payload)

        # Verify validation error
        assert response.status_code == 422
        data = response.json()
        assert "must be at least 2°F above" in data["detail"]
        assert "68" in data["detail"]  # Should mention current heat setpoint

    def test_post_zone_temperature_valid_2_degree_gap(
        self, client, mock_client, mock_mqtt_client, sample_status
    ):
        """Test that exactly 2°F gap is accepted."""
        # Configure mocks
        mock_client.set_zone_setpoints.return_value = None
        mock_client.get_status_data.return_value = sample_status
        mock_mqtt_client.publish_status.return_value = None

        # Set heat to 72 with existing cool=74 (exactly 2°F gap)
        payload = {
            "heat": 72,
            "temp": True,
        }

        # Make request
        response = client.post("/zones/1/temperature", json=payload)

        # Verify success
        assert response.status_code == 200

    @patch("pycz2.api.settings.CZ_ZONES", 4)  # Mock 4 zones for this test
    def test_post_zone_hold_success(
        self, client, mock_client, mock_mqtt_client, sample_status
    ):
        """Test successful POST /zones/{zone_id}/hold request."""
        # Configure mocks
        mock_client.set_zone_setpoints.return_value = None
        mock_client.get_status_data.return_value = sample_status
        mock_mqtt_client.publish_status.return_value = None

        # Request payload
        payload = {"hold": True, "temp": False}

        # Make request
        response = client.post("/zones/3/hold", json=payload)

        # Verify response - with cache enabled, returns structured format
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "meta" in data
        assert data["status"]["system_mode"] == "Auto"

        # Verify mock was called with correct arguments
        mock_client.set_zone_setpoints.assert_called_once_with(
            zones=[3], hold=True, temporary_hold=False
        )
        mock_client.get_status_data.assert_called_once()

    @patch("pycz2.api.settings.CZ_ZONES", 2)  # Mock 2 zones for this test
    def test_post_zone_hold_invalid_zone(self, client):
        """Test POST /zones/{zone_id}/hold with invalid zone ID."""
        # Request payload
        payload = {"hold": True}

        # Make request with invalid zone (zone 5 when only 2 zones exist)
        response = client.post("/zones/5/hold", json=payload)

        # Verify error response
        assert response.status_code == 404
        data = response.json()
        assert "Zone 5 not found" in data["detail"]

    def test_invalid_endpoint(self, client):
        """Test request to non-existent endpoint."""
        response = client.get("/nonexistent")
        assert response.status_code == 404

    def test_invalid_method(self, client):
        """Test invalid HTTP method on valid endpoint."""
        response = client.delete("/status")
        assert response.status_code == 405  # Method not allowed

    def test_malformed_json(self, client):
        """Test request with malformed JSON."""
        response = client.post(
            "/system/mode",
            content="invalid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_missing_required_field(self, client):
        """Test request missing required fields."""
        # SystemModeArgs requires 'mode' field
        payload = {
            "all": True
            # Missing required 'mode' field
        }

        response = client.post("/system/mode", json=payload)
        assert response.status_code == 422

    def test_client_exception_during_set_operation(self, client, mock_client):
        """Test exception during set operation."""
        # Configure mock to raise exception during set operation
        mock_client.set_system_mode.side_effect = Exception("Communication error")

        payload = {"mode": "Heat"}

        response = client.post("/system/mode", json=payload)

        # Should get 500 error since exception occurs before get_status_and_publish
        assert response.status_code == 500

    def test_retry_error_during_update_operation(
        self, client, mock_client, mock_mqtt_client
    ):
        """Test RetryError during update operation."""
        # Configure mocks - set succeeds but get_status_data fails
        mock_client.set_system_mode.return_value = None
        mock_client.get_status_data.side_effect = RetryError(None)

        payload = {"mode": "Heat"}

        response = client.post("/system/mode", json=payload)

        # With cache enabled and worker disabled, the error is caught and returns 500
        # The cache will be updated with error status
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
