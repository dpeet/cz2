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
                out=False
            ),
            ZoneStatus(
                zone_id=2,
                temperature=70,
                damper_position=50,
                cool_setpoint=74,
                heat_setpoint=68,
                temporary=False,
                hold=False,
                out=False
            )
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
            zones=zones
        )

    def test_get_status_success(self, client, mock_client, sample_status):
        """Test successful GET /status request."""
        # Configure mock to return sample status
        mock_client.get_status_data.return_value = sample_status
        
        # Make request
        response = client.get("/status")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Verify basic structure and values
        assert data["system_time"] == "Mon 02:30pm"
        assert data["system_mode"] == "Auto"
        assert data["effective_mode"] == "Cool"
        assert data["fan_mode"] == "Auto"
        assert data["fan_state"] == "On"
        assert data["active_state"] == "Cool On"
        assert data["all_mode"] is False
        assert data["outside_temp"] == 85
        assert data["air_handler_temp"] == 65
        assert data["zone1_humidity"] == 45
        assert len(data["zones"]) == 2
        
        # Verify zone data
        zone1 = data["zones"][0]
        assert zone1["zone_id"] == 1
        assert zone1["temperature"] == 72
        assert zone1["cool_setpoint"] == 74
        assert zone1["heat_setpoint"] == 68
        
        # Verify mock was called
        mock_client.get_status_data.assert_called_once()

    def test_get_status_retry_error(self, client, mock_client):
        """Test GET /status with RetryError from client."""
        # Configure mock to raise RetryError
        mock_client.get_status_data.side_effect = RetryError(None)
        
        # Make request
        response = client.get("/status")
        
        # Verify error response
        assert response.status_code == 504
        data = response.json()
        assert "Could not communicate with HVAC controller" in data["detail"]
        
        # Verify mock was called
        mock_client.get_status_data.assert_called_once()

    def test_get_status_general_exception(self, client, mock_client):
        """Test GET /status with general exception from client."""
        # Configure mock to raise general exception
        mock_client.get_status_data.side_effect = Exception("Connection failed")
        
        # Make request
        response = client.get("/status")
        
        # Verify error response
        assert response.status_code == 500
        data = response.json()
        assert "An internal server error occurred" in data["detail"]

    def test_post_update_success(self, client, mock_client, mock_mqtt_client, sample_status):
        """Test successful POST /update request."""
        # Configure mocks
        mock_client.get_status_data.return_value = sample_status
        mock_mqtt_client.publish_status.return_value = None
        
        # Make request
        response = client.post("/update")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["system_mode"] == "Auto"
        
        # Verify mocks were called
        mock_client.get_status_data.assert_called_once()

    def test_post_system_mode_success(self, client, mock_client, mock_mqtt_client, sample_status):
        """Test successful POST /system/mode request."""
        # Configure mocks
        mock_client.set_system_mode.return_value = None
        mock_client.get_status_data.return_value = sample_status
        mock_mqtt_client.publish_status.return_value = None
        
        # Request payload
        payload = {
            "mode": "Heat",
            "all": True
        }
        
        # Make request
        response = client.post("/system/mode", json=payload)
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["system_mode"] == "Auto"  # From sample_status
        
        # Verify mock was called with correct arguments
        mock_client.set_system_mode.assert_called_once_with(
            mode=SystemMode.HEAT,
            all_zones_mode=True
        )
        mock_client.get_status_data.assert_called_once()

    def test_post_system_mode_invalid_data(self, client):
        """Test POST /system/mode with invalid data."""
        # Invalid mode
        payload = {
            "mode": "InvalidMode"
        }
        
        # Make request
        response = client.post("/system/mode", json=payload)
        
        # Verify error response
        assert response.status_code == 422  # Validation error

    def test_post_system_fan_success(self, client, mock_client, mock_mqtt_client, sample_status):
        """Test successful POST /system/fan request."""
        # Configure mocks
        mock_client.set_fan_mode.return_value = None
        mock_client.get_status_data.return_value = sample_status
        mock_mqtt_client.publish_status.return_value = None
        
        # Request payload
        payload = {
            "fan": "On"
        }
        
        # Make request
        response = client.post("/system/fan", json=payload)
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["fan_mode"] == "Auto"  # From sample_status
        
        # Verify mock was called with correct arguments
        mock_client.set_fan_mode.assert_called_once_with(FanMode.ON)
        mock_client.get_status_data.assert_called_once()

    @patch('pycz2.api.settings.CZ_ZONES', 4)  # Mock 4 zones for this test
    def test_post_zone_temperature_success(self, client, mock_client, mock_mqtt_client, sample_status):
        """Test successful POST /zones/{zone_id}/temperature request."""
        # Configure mocks
        mock_client.set_zone_setpoints.return_value = None
        mock_client.get_status_data.return_value = sample_status
        mock_mqtt_client.publish_status.return_value = None
        
        # Request payload
        payload = {
            "heat": 70,
            "cool": 76,
            "temp": True,
            "hold": False,
            "out": False
        }
        
        # Make request
        response = client.post("/zones/2/temperature", json=payload)
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["system_mode"] == "Auto"
        
        # Verify mock was called with correct arguments
        mock_client.set_zone_setpoints.assert_called_once_with(
            zones=[2],
            heat_setpoint=70,
            cool_setpoint=76,
            temporary_hold=True,
            hold=False,
            out_mode=False
        )
        mock_client.get_status_data.assert_called_once()

    @patch('pycz2.api.settings.CZ_ZONES', 4)  # Mock 4 zones for this test
    def test_post_zone_temperature_invalid_zone(self, client):
        """Test POST /zones/{zone_id}/temperature with invalid zone ID."""
        # Request payload
        payload = {
            "heat": 70,
            "cool": 76
        }
        
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
            "cool": 76
        }
        
        # Make request
        response = client.post("/zones/1/temperature", json=payload)
        
        # Verify validation error
        assert response.status_code == 422

    @patch('pycz2.api.settings.CZ_ZONES', 4)  # Mock 4 zones for this test  
    def test_post_zone_hold_success(self, client, mock_client, mock_mqtt_client, sample_status):
        """Test successful POST /zones/{zone_id}/hold request."""
        # Configure mocks
        mock_client.set_zone_setpoints.return_value = None
        mock_client.get_status_data.return_value = sample_status
        mock_mqtt_client.publish_status.return_value = None
        
        # Request payload
        payload = {
            "hold": True,
            "temp": False
        }
        
        # Make request
        response = client.post("/zones/3/hold", json=payload)
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["system_mode"] == "Auto"
        
        # Verify mock was called with correct arguments
        mock_client.set_zone_setpoints.assert_called_once_with(
            zones=[3],
            hold=True,
            temporary_hold=False
        )
        mock_client.get_status_data.assert_called_once()

    @patch('pycz2.api.settings.CZ_ZONES', 2)  # Mock 2 zones for this test
    def test_post_zone_hold_invalid_zone(self, client):
        """Test POST /zones/{zone_id}/hold with invalid zone ID."""
        # Request payload
        payload = {
            "hold": True
        }
        
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
            data="invalid json",
            headers={"Content-Type": "application/json"}
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
        
        payload = {
            "mode": "Heat"
        }
        
        response = client.post("/system/mode", json=payload)
        
        # Should get 500 error since exception occurs before get_status_and_publish
        assert response.status_code == 500

    def test_retry_error_during_update_operation(self, client, mock_client, mock_mqtt_client):
        """Test RetryError during update operation."""
        # Configure mocks - set succeeds but get_status_data fails
        mock_client.set_system_mode.return_value = None
        mock_client.get_status_data.side_effect = RetryError(None)
        
        payload = {
            "mode": "Heat"
        }
        
        response = client.post("/system/mode", json=payload)
        
        # Should get 504 error from get_status_and_publish helper
        assert response.status_code == 504
        data = response.json()
        assert "Could not communicate with HVAC controller" in data["detail"]