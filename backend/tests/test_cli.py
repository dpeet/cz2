# tests/test_cli.py
from unittest.mock import AsyncMock

import pytest
from tenacity import RetryError
from typer.testing import CliRunner

from pycz2 import cli
from pycz2.core.client import ComfortZoneIIClient
from pycz2.core.constants import FanMode, SystemMode
from pycz2.core.models import SystemStatus, ZoneStatus


class TestCLIIntegration:
    """Integration tests for the CLI application."""

    @pytest.fixture
    def runner(self):
        """Create a CliRunner instance."""
        return CliRunner()

    @pytest.fixture
    def mock_client(self):
        """Create a mock ComfortZoneIIClient."""
        client = AsyncMock(spec=ComfortZoneIIClient)
        
        # Mock the context manager behavior
        client.connection.return_value.__aenter__ = AsyncMock(return_value=None)
        client.connection.return_value.__aexit__ = AsyncMock(return_value=None)
        
        return client

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
                cool_setpoint=76,
                heat_setpoint=66,
                temporary=True,
                hold=False,
                out=False
            ),
            ZoneStatus(
                zone_id=3,
                temperature=68,
                damper_position=25,
                cool_setpoint=72,
                heat_setpoint=64,
                temporary=False,
                hold=True,
                out=False
            ),
            ZoneStatus(
                zone_id=4,
                temperature=0,
                damper_position=0,
                cool_setpoint=72,
                heat_setpoint=64,
                temporary=False,
                hold=False,
                out=True
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
            compressor_stage_1=False,
            compressor_stage_2=False,
            aux_heat_stage_1=False,
            aux_heat_stage_2=False,
            humidify=False,
            dehumidify=False,
            reversing_valve=False,
            raw=None,
            zones=zones
        )

    def test_status_command_success(self, runner, mock_client, sample_status, monkeypatch):
        """Test successful status command execution."""
        # Configure mock
        mock_client.get_status_data.return_value = sample_status
        
        # Patch the get_client function
        async def mock_get_client():
            return mock_client
        
        monkeypatch.setattr(cli, "get_client", mock_get_client)
        
        # Run command
        result = runner.invoke(cli.app, ["status"])
        
        # Verify exit code
        assert result.exit_code == 0
        
        # Verify key content in output
        assert "System Time:" in result.stdout
        assert "Mon 02:30pm" in result.stdout
        assert "Outside 85°F" in result.stdout
        assert "Indoor humidity 45%" in result.stdout
        assert "65°F, Fan On, Cool On" in result.stdout
        assert "Auto (Cool), Fan Auto" in result.stdout
        
        # Verify zone table content
        assert "Zone" in result.stdout  # Table header
        assert "Temp (°F)" in result.stdout  # Table header
        assert "Damper (%)" in result.stdout  # Table header
        assert "Setpoint" in result.stdout  # Table header
        assert "Mode" in result.stdout  # Table header
        
        # Verify zone data appears in output
        assert "Zone 1" in result.stdout
        assert "Zone 2" in result.stdout
        assert "Zone 3" in result.stdout
        assert "Zone 4" in result.stdout
        assert "72" in result.stdout  # Zone 1 temperature
        assert "70" in result.stdout  # Zone 2 temperature
        assert "[TEMP]" in result.stdout  # Zone 2 temporary mode
        assert "[HOLD]" in result.stdout  # Zone 3 hold mode
        assert "OUT" in result.stdout  # Zone 4 out mode
        
        # Verify mock was called
        mock_client.get_status_data.assert_called_once()

    def test_status_command_failure(self, runner, mock_client, monkeypatch):
        """Test status command with client failure."""
        # Configure mock to raise RetryError
        mock_client.get_status_data.side_effect = RetryError(None)
        
        # Patch the get_client function
        async def mock_get_client():
            return mock_client
        
        monkeypatch.setattr(cli, "get_client", mock_get_client)
        
        # Run command
        result = runner.invoke(cli.app, ["status"])
        
        # Verify exit code indicates failure
        assert result.exit_code != 0
        
        # Verify mock was called
        mock_client.get_status_data.assert_called_once()

    def test_status_json_command_success(self, runner, mock_client, sample_status, monkeypatch):
        """Test successful status-json command execution."""
        # Configure mock
        mock_client.get_status_data.return_value = sample_status
        
        # Patch the get_client function
        async def mock_get_client():
            return mock_client
        
        monkeypatch.setattr(cli, "get_client", mock_get_client)
        
        # Run command
        result = runner.invoke(cli.app, ["status-json"])
        
        # Verify exit code
        assert result.exit_code == 0
        
        # Verify JSON content in output
        assert '"system_time": "Mon 02:30pm"' in result.stdout
        assert '"system_mode": "Auto"' in result.stdout
        assert '"outside_temp": 85' in result.stdout
        assert '"zones":' in result.stdout
        assert '"raw"' not in result.stdout

        # Verify mock was called
        mock_client.get_status_data.assert_called_once_with(include_raw=False)

    def test_status_json_command_with_raw(self, runner, mock_client, sample_status, monkeypatch):
        """status-json should include raw blob when requested."""
        raw_blob = "QUJD"
        mock_client.get_status_data.return_value = sample_status.model_copy(update={"raw": raw_blob})

        async def mock_get_client():
            return mock_client

        monkeypatch.setattr(cli, "get_client", mock_get_client)

        result = runner.invoke(cli.app, ["status-json", "--raw"])

        assert result.exit_code == 0
        assert f'"raw": "{raw_blob}"' in result.stdout
        mock_client.get_status_data.assert_called_once_with(include_raw=True)

    def test_set_system_command_success(self, runner, mock_client, sample_status, monkeypatch):
        """Test successful set-system command execution."""
        # Configure mocks
        mock_client.set_system_mode.return_value = None
        mock_client.set_fan_mode.return_value = None
        mock_client.get_status_data.return_value = sample_status
        
        # Patch the get_client function
        async def mock_get_client():
            return mock_client
        
        monkeypatch.setattr(cli, "get_client", mock_get_client)
        
        # Run command
        result = runner.invoke(cli.app, ["set-system", "--mode", "Heat", "--fan", "On", "--all"])
        
        # Verify exit code
        assert result.exit_code == 0
        
        # Verify success message and status display
        assert "System settings updated" in result.stdout
        assert "New status:" in result.stdout
        assert "System Time:" in result.stdout
        
        # Verify mock calls
        mock_client.set_system_mode.assert_called_once_with(SystemMode.HEAT, True)
        mock_client.set_fan_mode.assert_called_once_with(FanMode.ON)
        mock_client.get_status_data.assert_called_once()

    def test_set_system_command_no_options(self, runner, monkeypatch):
        """Test set-system command with no options specified."""
        # Patch the get_client function (though it shouldn't be called)
        async def mock_get_client():
            return AsyncMock()
        
        monkeypatch.setattr(cli, "get_client", mock_get_client)
        
        # Run command with no options
        result = runner.invoke(cli.app, ["set-system"])
        
        # Verify exit code indicates failure
        assert result.exit_code == 1
        
        # Verify error message
        assert "No options specified" in result.stdout

    def test_set_system_command_invalid_mode(self, runner):
        """Test set-system command with invalid mode."""
        # Run command with invalid mode
        result = runner.invoke(cli.app, ["set-system", "--mode", "invalid-mode"])
        
        # Verify exit code indicates validation error
        assert result.exit_code == 2
        
        # Verify error message contains information about invalid choice
        assert "Invalid value" in result.stderr or "invalid-mode" in result.stderr

    def test_set_zone_command_success(self, runner, mock_client, sample_status, monkeypatch):
        """Test successful set-zone command execution."""
        # Configure mocks
        mock_client.set_zone_setpoints.return_value = None
        mock_client.get_status_data.return_value = sample_status
        
        # Patch the get_client function
        async def mock_get_client():
            return mock_client
        
        monkeypatch.setattr(cli, "get_client", mock_get_client)
        
        # Run command
        result = runner.invoke(cli.app, ["set-zone", "1", "3", "--heat", "70", "--cool", "76", "--temp"])
        
        # Verify exit code
        assert result.exit_code == 0
        
        # Verify success message and status display
        assert "Zone settings updated" in result.stdout
        assert "New status:" in result.stdout
        assert "System Time:" in result.stdout
        
        # Verify mock was called with correct arguments
        mock_client.set_zone_setpoints.assert_called_once_with(
            zones=[1, 3],
            heat_setpoint=70,
            cool_setpoint=76,
            temporary_hold=True,
            hold=False,
            out_mode=False
        )
        mock_client.get_status_data.assert_called_once()

    def test_set_zone_command_single_zone(self, runner, mock_client, sample_status, monkeypatch):
        """Test set-zone command with single zone and hold option."""
        # Configure mocks
        mock_client.set_zone_setpoints.return_value = None
        mock_client.get_status_data.return_value = sample_status
        
        # Patch the get_client function
        async def mock_get_client():
            return mock_client
        
        monkeypatch.setattr(cli, "get_client", mock_get_client)
        
        # Run command
        result = runner.invoke(cli.app, ["set-zone", "2", "--heat", "68", "--hold", "--out"])
        
        # Verify exit code
        assert result.exit_code == 0
        
        # Verify mock was called with correct arguments
        mock_client.set_zone_setpoints.assert_called_once_with(
            zones=[2],
            heat_setpoint=68,
            cool_setpoint=None,
            temporary_hold=False,
            hold=True,
            out_mode=True
        )

    def test_read_command_success(self, runner, mock_client, monkeypatch):
        """Test successful read command execution."""
        # Create a mock frame object
        mock_frame = AsyncMock()
        mock_frame.data = [0, 1, 16, 74, 74, 68, 68]
        
        # Configure mock
        mock_client.read_row.return_value = mock_frame
        
        # Patch the get_client function
        async def mock_get_client():
            return mock_client
        
        monkeypatch.setattr(cli, "get_client", mock_get_client)
        
        # Run command
        result = runner.invoke(cli.app, ["read", "1", "1", "16"])
        
        # Verify exit code
        assert result.exit_code == 0
        
        # Verify output contains the frame data
        assert "0.1.16.74.74.68.68" in result.stdout
        
        # Verify mock was called with correct arguments
        mock_client.read_row.assert_called_once_with(1, 1, 16)

    def test_monitor_command_setup(self, runner, mock_client, monkeypatch):
        """Test monitor command setup (without actually monitoring)."""
        # Create an async generator that yields one frame then stops
        async def mock_monitor_bus():
            mock_frame = AsyncMock()
            mock_frame.source = 1
            mock_frame.destination = 9
            mock_frame.function.name = "read"
            mock_frame.data = [0, 1, 16]
            yield mock_frame
            # End the generator to avoid infinite loop in test
        
        # Configure mock
        mock_client.monitor_bus.return_value = mock_monitor_bus()
        
        # Patch the get_client function
        async def mock_get_client():
            return mock_client
        
        monkeypatch.setattr(cli, "get_client", mock_get_client)
        
        # Run command (this will run until the generator is exhausted)
        result = runner.invoke(cli.app, ["monitor"])
        
        # Verify exit code
        assert result.exit_code == 0
        
        # Verify monitoring setup message
        assert "Monitoring bus traffic" in result.stdout
        
        # Verify frame output format
        assert "01 -> 09" in result.stdout
        assert "read" in result.stdout
        assert "0.1.16" in result.stdout

    def test_invalid_command(self, runner):
        """Test execution of non-existent command."""
        result = runner.invoke(cli.app, ["nonexistent"])
        
        # Verify exit code indicates command not found
        assert result.exit_code == 2
        
        # Verify error message
        assert "No such command" in result.stderr or "Usage:" in result.stdout

    def test_help_output(self, runner):
        """Test help output for main app."""
        result = runner.invoke(cli.app, ["--help"])
        
        # Verify exit code
        assert result.exit_code == 0
        
        # Verify help content
        assert "Command-Line Interface for interacting with the HVAC system" in result.stdout
        assert "status" in result.stdout
        assert "set-system" in result.stdout
        assert "set-zone" in result.stdout
        assert "monitor" in result.stdout
        assert "read" in result.stdout

    def test_status_command_help(self, runner):
        """Test help output for status command."""
        result = runner.invoke(cli.app, ["status", "--help"])
        
        # Verify exit code
        assert result.exit_code == 0
        
        # Verify help content
        assert "Print an overview of the current system status" in result.stdout

    def test_set_zone_command_help(self, runner):
        """Test help output for set-zone command."""
        result = runner.invoke(cli.app, ["set-zone", "--help"])
        
        # Verify exit code
        assert result.exit_code == 0
        
        # Verify help content
        assert "Set options for one or more zones" in result.stdout
        assert "--heat" in result.stdout
        assert "--cool" in result.stdout
        assert "--temp" in result.stdout
        assert "--hold" in result.stdout
        assert "--out" in result.stdout

    def test_set_zone_invalid_temperature(self, runner):
        """Test set-zone command with invalid temperature values."""
        # Test with heat setpoint too low
        result = runner.invoke(cli.app, ["set-zone", "1", "--heat", "30"])
        
        # Should fail due to validation (though this depends on Typer's validation)
        # The exact exit code may vary, but it should not be 0
        assert result.exit_code != 0

    def test_set_zone_missing_zones(self, runner):
        """Test set-zone command without specifying zones."""
        result = runner.invoke(cli.app, ["set-zone", "--heat", "70"])
        
        # Should fail because zones argument is required
        assert result.exit_code == 2

    def test_client_connection_error(self, runner, mock_client, monkeypatch):
        """Test command execution when client connection fails."""
        # Configure mock to raise exception during connection
        mock_client.connection.side_effect = Exception("Connection failed")
        
        # Patch the get_client function
        async def mock_get_client():
            return mock_client
        
        monkeypatch.setattr(cli, "get_client", mock_get_client)
        
        # Run command
        result = runner.invoke(cli.app, ["status"])
        
        # Verify exit code indicates failure
        assert result.exit_code != 0

    def test_no_args_shows_help(self, runner):
        """Test that running CLI with no arguments shows help."""
        result = runner.invoke(cli.app, [])
        
        # Verify that help is shown (exit code 0 for help display)
        assert result.exit_code == 0
        assert "Usage:" in result.stdout
        assert "Command-Line Interface for interacting with the HVAC system" in result.stdout
