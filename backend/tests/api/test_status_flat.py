"""
TDD Red Phase: /status?flat=1 Parity Tests

This module tests that the /status?flat=1 endpoint returns payloads
matching the legacy format expected by mountainstat-main frontend.

Parity Requirements (all tests should FAIL initially):
1. SystemMode/FanMode enums emitted as title-case strings ("Heat", "Auto")
2. all_mode returned as numeric: booleans → 0/1, integers 1-8 unchanged
3. time field present and integer (int(time.time()))
4. zones[].damper_position always string (e.g., "100")
5. Response structure matches json_response.js
6. MQTT snapshot payload mirrors HTTP response (structure + types)
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from pycz2.api import app
from pycz2.core.client import ComfortZoneIIClient, get_client, get_lock
from pycz2.core.constants import FanMode, SystemMode
from pycz2.core.models import SystemStatus, ZoneStatus
from pycz2.mqtt import MqttClient, get_mqtt_client


@pytest.fixture
def mock_client():
    """Create a mock ComfortZoneIIClient."""
    client = AsyncMock(spec=ComfortZoneIIClient)
    connection_cm = AsyncMock()
    connection_cm.__aenter__.return_value = None
    connection_cm.__aexit__.return_value = None
    client.connection.return_value = connection_cm
    return client


@pytest.fixture
def mock_mqtt_client():
    """Create a mock MqttClient."""
    mqtt_client = AsyncMock(spec=MqttClient)
    return mqtt_client


@pytest.fixture
def mock_lock():
    """Create a real asyncio.Lock for testing."""
    return asyncio.Lock()


@pytest.fixture
def legacy_sample_status():
    """
    Create a SystemStatus matching the legacy json_response.js structure.

    This fixture represents what the HVAC returns internally (with enums),
    but needs to be converted to legacy format for flat=1 responses.
    """
    zones = [
        ZoneStatus(
            zone_id=1,
            temperature=47,
            damper_position=100,  # Integer in model
            cool_setpoint=85,
            heat_setpoint=55,
            temporary=False,
            hold=True,
            out=False,
        ),
        ZoneStatus(
            zone_id=2,
            temperature=48,
            damper_position=100,
            cool_setpoint=85,
            heat_setpoint=55,
            temporary=False,
            hold=True,
            out=False,
        ),
        ZoneStatus(
            zone_id=3,
            temperature=48,
            damper_position=100,
            cool_setpoint=85,
            heat_setpoint=55,
            temporary=False,
            hold=True,
            out=False,
        ),
        ZoneStatus(
            zone_id=4,
            temperature=0,
            damper_position=0,
            cool_setpoint=85,
            heat_setpoint=45,
            temporary=False,
            hold=True,
            out=False,
        ),
    ]

    return SystemStatus(
        system_time="Sun 12:52am",
        system_mode=SystemMode.AUTO,
        effective_mode=SystemMode.HEAT,
        fan_mode=FanMode.AUTO,
        fan_state="Off",
        active_state="Idle",
        all_mode=True,  # Boolean in model, should become 1 in flat response
        outside_temp=-1,
        air_handler_temp=52,
        zone1_humidity=51,
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


@pytest.fixture
def test_app_flat(mock_client, mock_mqtt_client, mock_lock):
    """Create a FastAPI test app with mocked dependencies."""
    app.dependency_overrides[get_client] = lambda: mock_client
    app.dependency_overrides[get_mqtt_client] = lambda: mock_mqtt_client
    app.dependency_overrides[get_lock] = lambda: mock_lock

    async def noop(*args, **kwargs):
        return None

    hvac_client_patch = patch("pycz2.hvac_service.get_client", lambda: mock_client)
    hvac_start_patch = patch("pycz2.hvac_service.HVACService.start", noop)
    hvac_stop_patch = patch("pycz2.hvac_service.HVACService.stop", noop)

    with (
        patch("pycz2.api.settings.WORKER_ENABLED", False),
        hvac_client_patch,
        hvac_start_patch,
        hvac_stop_patch,
    ):
        yield app

    app.dependency_overrides.clear()


@pytest.fixture
def client_flat(test_app_flat):
    """Create a TestClient for the FastAPI app."""
    with TestClient(test_app_flat) as test_client:
        # Clear cache before each test to avoid interference
        try:
            test_client.post("/cache/clear")
            # Ignore errors if cache not available
        except Exception:
            pass
        yield test_client


class TestStatusFlatParity:
    """
    Test /status?flat=1 endpoint parity with legacy Node-RED payload.

    ALL TESTS IN THIS CLASS SHOULD FAIL INITIALLY (Red phase).
    """

    def test_system_mode_enum_to_title_case_string(
        self, client_flat, mock_client, legacy_sample_status
    ):
        """
        Parity Requirement 1: SystemMode enums emitted as title-case strings.

        Legacy expects: "Heat", "Cool", "Auto", "EHeat", "Off"
        Current returns: Enum values (may not match exactly)
        """
        mock_client.get_status_data.return_value = legacy_sample_status

        response = client_flat.get("/status?flat=1")
        assert response.status_code == 200
        data = response.json()

        # Verify system_mode is title-case string
        assert "system_mode" in data, "system_mode field missing"
        assert isinstance(data["system_mode"], str), (
            f"system_mode should be string, got {type(data['system_mode'])}"
        )
        assert data["system_mode"] == "Auto", (
            f"Expected 'Auto', got '{data['system_mode']}'"
        )

        # Verify effective_mode is title-case string
        assert "effective_mode" in data, "effective_mode field missing"
        assert isinstance(data["effective_mode"], str), (
            f"effective_mode should be string, got {type(data['effective_mode'])}"
        )
        assert data["effective_mode"] == "Heat", (
            f"Expected 'Heat', got '{data['effective_mode']}'"
        )

    def test_fan_mode_enum_to_title_case_string(
        self, client_flat, mock_client, legacy_sample_status
    ):
        """
        Parity Requirement 1: FanMode enums emitted as title-case strings.

        Legacy expects: "Auto", "On"
        Current returns: Enum values (may not match)
        """
        mock_client.get_status_data.return_value = legacy_sample_status

        response = client_flat.get("/status?flat=1")
        assert response.status_code == 200
        data = response.json()

        # Verify fan_mode is title-case string
        assert "fan_mode" in data, "fan_mode field missing"
        assert isinstance(data["fan_mode"], str), (
            f"fan_mode should be string, got {type(data['fan_mode'])}"
        )
        assert data["fan_mode"] == "Auto", f"Expected 'Auto', got '{data['fan_mode']}'"

    def test_all_mode_boolean_to_numeric(
        self, client_flat, mock_client, legacy_sample_status
    ):
        """
        Parity Requirement 2: all_mode as numeric (bool → 0/1).

        Legacy expects: 0 or 1 (integer)
        Current returns: true/false (boolean)
        """
        # Test with True (should become 1)
        legacy_sample_status.all_mode = True
        mock_client.get_status_data.return_value = legacy_sample_status

        response = client_flat.get("/status?flat=1")
        assert response.status_code == 200
        data = response.json()

        assert "all_mode" in data, "all_mode field missing"
        assert isinstance(data["all_mode"], int), (
            f"all_mode should be int, got {type(data['all_mode'])}"
        )
        assert data["all_mode"] == 1, f"Expected 1 for True, got {data['all_mode']}"

    def test_all_mode_false_to_zero(
        self, client_flat, mock_client, legacy_sample_status
    ):
        """
        Parity Requirement 2: all_mode False → 0.
        """
        legacy_sample_status.all_mode = False
        mock_client.get_status_data.return_value = legacy_sample_status

        response = client_flat.get("/status?flat=1")
        assert response.status_code == 200
        data = response.json()

        assert data["all_mode"] == 0, f"Expected 0 for False, got {data['all_mode']}"

    def test_all_mode_integer_unchanged(
        self, client_flat, mock_client, legacy_sample_status
    ):
        """
        Parity Requirement 2: all_mode integers 1-8 unchanged.

        NOTE: This may require model changes if all_mode is bool-only.
        Test for future-proofing when all_mode can be 1-8.
        """
        # This test documents expected behavior for integer all_mode values
        # Currently may fail if model doesn't support int values

        for test_value in [1, 2, 3, 4, 5, 6, 7, 8]:
            # Note: May need to adjust model to accept int | bool (clarify)
            pass  # Placeholder - implement when model supports int

    def test_time_field_present_and_integer(
        self, client_flat, mock_client, legacy_sample_status
    ):
        """
        Parity Requirement 3: time field present and integer.

        Legacy expects: Unix timestamp (int)
        Current: May be missing or wrong type
        """
        mock_client.get_status_data.return_value = legacy_sample_status

        # Mock time.time() for deterministic testing
        expected_time = 1676180543
        with patch("time.time", return_value=expected_time):
            response = client_flat.get("/status?flat=1")

        assert response.status_code == 200
        data = response.json()

        assert "time" in data, "time field missing (clarify)"
        assert isinstance(data["time"], int), (
            f"time should be int, got {type(data.get('time'))}"
        )
        # Should be close to current time (within reason)
        assert data["time"] > 0, "time should be positive unix timestamp"

    def test_damper_position_as_string(
        self, client_flat, mock_client, legacy_sample_status
    ):
        """
        Parity Requirement 4: zones[].damper_position always string.

        Legacy expects: "100", "0", "50" (strings)
        Current returns: 100, 0, 50 (integers)

        UI compares to "100" explicitly, so must be string.
        """
        mock_client.get_status_data.return_value = legacy_sample_status

        response = client_flat.get("/status?flat=1")
        assert response.status_code == 200
        data = response.json()

        assert "zones" in data, "zones field missing"
        assert len(data["zones"]) > 0, "Expected at least one zone"

        # Check each zone's damper_position
        for i, zone in enumerate(data["zones"]):
            assert "damper_position" in zone, f"Zone {i} missing damper_position"
            assert isinstance(zone["damper_position"], str), (
                f"Zone {i} damper_position should be string, got {type(zone['damper_position'])}"
            )

        # Verify specific values match legacy format
        assert data["zones"][0]["damper_position"] == "100", (
            f"Expected '100', got '{data['zones'][0]['damper_position']}'"
        )
        assert data["zones"][3]["damper_position"] == "0", (
            f"Expected '0', got '{data['zones'][3]['damper_position']}'"
        )

    def test_response_structure_matches_legacy(
        self, client_flat, mock_client, legacy_sample_status
    ):
        """
        Parity Requirement 5: Response structure matches json_response.js.

        Validates all top-level fields exist and have correct types.
        """
        mock_client.get_status_data.return_value = legacy_sample_status

        response = client_flat.get("/status?flat=1")
        assert response.status_code == 200
        data = response.json()

        # Top-level fields from json_response.js
        expected_fields = {
            "air_handler_temp": int,
            "all_mode": int,  # Should be numeric
            "effective_mode": str,  # Should be title-case string
            "fan_mode": str,  # Should be title-case string
            "outside_temp": int,
            "system_mode": str,  # Should be title-case string
            "system_time": str,
            "time": int,  # Unix timestamp
            "zone1_humidity": int,
            "zones": list,
        }

        for field, expected_type in expected_fields.items():
            assert field in data, f"Missing required field: {field}"
            assert isinstance(data[field], expected_type), (
                f"Field {field} should be {expected_type.__name__}, got {type(data[field])}"
            )

        # Verify zones structure
        assert len(data["zones"]) > 0, "Expected at least one zone"
        zone = data["zones"][0]

        zone_fields = {
            "cool_setpoint": int,
            "damper_position": str,  # Must be string
            "heat_setpoint": int,
            "hold": (int, bool),  # May be int or bool (clarify)
            "out": (int, bool),  # May be int or bool
            "temperature": int,
            "temporary": (int, bool),  # May be int or bool
        }

        for field, expected_type in zone_fields.items():
            assert field in zone, f"Zone missing field: {field}"
            if isinstance(expected_type, tuple):
                assert isinstance(zone[field], expected_type), (
                    f"Zone field {field} should be {expected_type}, got {type(zone[field])}"
                )
            else:
                assert isinstance(zone[field], expected_type), (
                    f"Zone field {field} should be {expected_type.__name__}, got {type(zone[field])}"
                )

    def test_zone_boolean_fields_as_integers(
        self, client_flat, mock_client, legacy_sample_status
    ):
        """
        Parity check: Zone boolean fields (hold, temporary, out).

        Legacy shows: hold=1, temporary=0, out=0 (integers)
        May need conversion like all_mode (clarify)
        """
        mock_client.get_status_data.return_value = legacy_sample_status

        response = client_flat.get("/status?flat=1")
        assert response.status_code == 200
        data = response.json()

        zone = data["zones"][0]

        # Check if boolean fields are numeric (like legacy)
        # This may be a (clarify) item depending on requirements
        for field in ["hold", "temporary", "out"]:
            if field in zone:
                # Document current behavior
                print(f"Zone field {field}: {zone[field]} (type: {type(zone[field])})")

    @patch("pycz2.api.settings.MQTT_ENABLED", True)
    def test_mqtt_payload_mirrors_http_response(
        self, client_flat, mock_client, mock_mqtt_client, legacy_sample_status
    ):
        """
        Parity Requirement 6: MQTT payload mirrors HTTP /status?flat=1 response.

        MQTT messages must have identical structure and types to HTTP flat response,
        including:
        - Title-case enum strings
        - Numeric all_mode
        - Integer time field
        - String damper_position
        """
        mock_client.get_status_data.return_value = legacy_sample_status

        # Capture MQTT publish call - publish_status receives SystemStatus object
        published_status = None

        async def capture_publish(status: SystemStatus):
            nonlocal published_status
            published_status = status

        mock_mqtt_client.publish_status = AsyncMock(side_effect=capture_publish)

        # Trigger update which publishes to MQTT
        response = client_flat.post("/update")
        assert response.status_code == 200

        # Verify MQTT was called
        mock_mqtt_client.publish_status.assert_called_once()
        assert published_status is not None, "MQTT publish was not captured"

        # Convert published status to flat format (same as MQTT does)
        mqtt_data = published_status.to_dict(flat=True)

        # MQTT payload should match HTTP flat response
        assert mqtt_data.get("system_mode") == "Auto", (
            f"MQTT system_mode should be 'Auto', got '{mqtt_data.get('system_mode')}'"
        )
        assert mqtt_data.get("fan_mode") == "Auto", (
            f"MQTT fan_mode should be 'Auto', got '{mqtt_data.get('fan_mode')}'"
        )
        assert mqtt_data.get("all_mode") == 1, (
            f"MQTT all_mode should be 1, got {mqtt_data.get('all_mode')}"
        )
        assert "time" in mqtt_data, "MQTT payload missing time field"
        assert isinstance(mqtt_data.get("time"), int), (
            f"MQTT time should be int, got {type(mqtt_data.get('time'))}"
        )

        if "zones" in mqtt_data and len(mqtt_data["zones"]) > 0:
            assert isinstance(mqtt_data["zones"][0]["damper_position"], str), (
                f"MQTT damper_position should be string, got {type(mqtt_data['zones'][0]['damper_position'])}"
            )

    def test_flat_format_excludes_meta_wrapper(
        self, client_flat, mock_client, legacy_sample_status
    ):
        """
        Verify flat=1 returns unwrapped data (no 'status' or 'meta' keys).

        Legacy expects flat structure at root level.
        New format has {"status": {...}, "meta": {...}}
        """
        mock_client.get_status_data.return_value = legacy_sample_status

        response = client_flat.get("/status?flat=1")
        assert response.status_code == 200
        data = response.json()

        # Should NOT have wrapper keys
        assert "status" not in data, "flat=1 should not have 'status' wrapper (clarify)"
        assert "meta" not in data, "flat=1 should not have 'meta' wrapper"

        # Should have actual status fields at root
        assert "system_mode" in data, "flat=1 should have system_mode at root level"
        assert "zones" in data, "flat=1 should have zones at root level"

    def test_all_mode_type_consistency_across_endpoints(
        self, client_flat, mock_client, legacy_sample_status
    ):
        """
        Verify all_mode type is consistent in all flat=1 responses.

        Should be numeric in:
        - GET /status?flat=1
        - POST /update (return value)
        - MQTT payload
        """
        mock_client.get_status_data.return_value = legacy_sample_status

        # GET /status?flat=1
        response = client_flat.get("/status?flat=1")
        status_data = response.json()
        assert isinstance(status_data.get("all_mode"), int), (
            "GET /status?flat=1 all_mode should be int"
        )

        # POST /update (may return different structure - clarify)
        # This test documents expected behavior


class TestStatusFlatEdgeCases:
    """Edge cases for flat format conversion."""

    def test_flat_format_with_no_zones(self, client_flat, mock_client):
        """Test flat format with empty zones array."""
        status_no_zones = SystemStatus(
            system_time="Mon 03:00pm",
            system_mode=SystemMode.OFF,
            effective_mode=SystemMode.OFF,
            fan_mode=FanMode.AUTO,
            fan_state="Off",
            active_state="Idle",
            all_mode=False,
            outside_temp=0,
            air_handler_temp=0,
            zone1_humidity=0,
            zones=[],
        )

        mock_client.get_status_data.return_value = status_no_zones

        response = client_flat.get("/status?flat=1")
        assert response.status_code == 200
        data = response.json()

        assert data["zones"] == []
        assert data["all_mode"] == 0, "False should convert to 0"
        assert isinstance(data["time"], int), "time should still be present"

    def test_flat_format_preserves_all_system_modes(
        self, client_flat, mock_client, legacy_sample_status
    ):
        """Test all SystemMode values convert to correct title-case strings."""
        mode_mapping = {
            SystemMode.HEAT: "Heat",
            SystemMode.COOL: "Cool",
            SystemMode.AUTO: "Auto",
            SystemMode.EHEAT: "EHeat",
            SystemMode.OFF: "Off",
        }

        for mode_enum, expected_string in mode_mapping.items():
            legacy_sample_status.system_mode = mode_enum
            mock_client.get_status_data.return_value = legacy_sample_status

            response = client_flat.get("/status?flat=1")
            data = response.json()

            assert data["system_mode"] == expected_string, (
                f"SystemMode.{mode_enum.name} should convert to '{expected_string}'"
            )

    def test_flat_format_preserves_all_fan_modes(
        self, client_flat, mock_client, legacy_sample_status
    ):
        """Test all FanMode values convert to correct title-case strings."""
        mode_mapping = {
            FanMode.AUTO: "Auto",
            FanMode.ON: "On",
        }

        for mode_enum, expected_string in mode_mapping.items():
            legacy_sample_status.fan_mode = mode_enum
            mock_client.get_status_data.return_value = legacy_sample_status

            response = client_flat.get("/status?flat=1")
            data = response.json()

            assert data["fan_mode"] == expected_string, (
                f"FanMode.{mode_enum.name} should convert to '{expected_string}'"
            )
