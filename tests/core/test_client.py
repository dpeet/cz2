# tests/core/test_client.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tenacity import RetryError

from pycz2.core.client import ComfortZoneIIClient
from pycz2.core.constants import FanMode, Function, SystemMode
from pycz2.core.frame import build_message
from pycz2.core.models import SystemStatus


class TestComfortZoneIIClient:
    """Test cases for ComfortZoneIIClient."""

    @pytest.fixture
    def mock_reader(self):
        """Create a mock StreamReader."""
        reader = MagicMock()
        reader.read = AsyncMock(return_value=b"")
        return reader

    @pytest.fixture
    def mock_writer(self):
        """Create a mock StreamWriter."""
        writer = MagicMock()
        writer.is_closing = MagicMock(return_value=False)
        writer.close = MagicMock(return_value=None)
        writer.wait_closed = AsyncMock(return_value=None)
        writer.write = MagicMock(return_value=None)
        writer.drain = AsyncMock(return_value=None)
        writer.get_extra_info = MagicMock(return_value=None)
        return writer

    @pytest.fixture
    def client(self):
        """Create a ComfortZoneIIClient instance."""
        return ComfortZoneIIClient(
            connect_str="localhost:8080",
            zone_count=4,
            device_id=99
        )

    @pytest.fixture
    def serial_client(self):
        """Create a ComfortZoneIIClient instance for serial connection."""
        return ComfortZoneIIClient(
            connect_str="/dev/ttyUSB0",
            zone_count=4,
            device_id=99
        )

    def create_mock_frame_data(self, dest: int, source: int, func: Function, data: list[int]) -> bytes:
        """Helper to create valid frame data for mocking."""
        return build_message(dest, source, func, data)

    def create_status_mock_data(self) -> dict[str, bytes]:
        """Create mock frame data for all READ_QUERIES needed for status."""
        mock_frames = {}
        
        # Mock data for each query in READ_QUERIES
        queries_data = {
            "9.9.3": [0, 9, 3, 0, 0, 0, 0, 65, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # Outside temp data
            "9.9.4": [0, 9, 4, 15, 12, 8, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # Damper positions
            "9.9.5": [0, 9, 5, 32, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # Panel status (fan on)
            "1.1.9": [0, 1, 9, 0, 45, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # Zone 1 humidity
            "1.1.12": [0, 1, 12, 0, 2, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # System mode
            "1.1.16": [0, 1, 16, 74, 74, 74, 74, 0, 0, 0, 0, 68, 68, 68, 68, 0, 0, 0, 0],  # Setpoints
            "1.1.17": [0, 1, 17, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # Fan mode
            "1.1.18": [0, 1, 18, 2, 14, 30, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # Time
            "1.1.24": [0, 1, 24, 72, 70, 68, 66, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # Zone temps
        }
        
        for query, data in queries_data.items():
            dest, table, row = map(int, query.split("."))
            mock_frames[query] = self.create_mock_frame_data(99, dest, Function.reply, data)
        
        return mock_frames

    @pytest.mark.asyncio
    async def test_tcp_connection(self, client, mock_reader, mock_writer):
        """Test TCP connection establishment."""
        with patch('asyncio.open_connection', return_value=(mock_reader, mock_writer)) as mock_open:
            await client.connect()
            
            mock_open.assert_called_once_with('localhost', 8080)
            assert client.reader == mock_reader
            assert client.writer == mock_writer
            assert client.is_connected()

    @pytest.mark.asyncio
    async def test_serial_connection(self, serial_client, mock_reader, mock_writer):
        """Test serial connection establishment."""
        with patch('pyserial_asyncio.open_serial_connection', return_value=(mock_reader, mock_writer)) as mock_open:
            await serial_client.connect()
            
            mock_open.assert_called_once_with(
                url='/dev/ttyUSB0',
                baudrate=9600,
                bytesize=8,
                parity='N',
                stopbits=1
            )
            assert serial_client.reader == mock_reader
            assert serial_client.writer == mock_writer

    @pytest.mark.asyncio
    async def test_connection_failure(self, client):
        """Test connection failure handling."""
        with patch('asyncio.open_connection', side_effect=OSError("Connection failed")):
            with pytest.raises(OSError, match="Connection failed"):
                await client.connect()

    @pytest.mark.asyncio
    async def test_close_connection(self, client, mock_reader, mock_writer):
        """Test connection closure."""
        client.reader = mock_reader
        client.writer = mock_writer
        
        await client.close()
        
        mock_writer.close.assert_called_once()
        mock_writer.wait_closed.assert_called_once()
        assert client.reader is None
        assert client.writer is None

    @pytest.mark.asyncio
    async def test_get_status_data(self, client, mock_reader, mock_writer):
        """Test successful status data retrieval and parsing."""
        # Setup mock data
        mock_frames = self.create_status_mock_data()
        
        # Configure mock reader to return frames in sequence
        frame_sequence = []
        for query in ["9.9.3", "9.9.4", "9.9.5", "1.1.9", "1.1.12", "1.1.16", "1.1.17", "1.1.18", "1.1.24"]:
            frame_sequence.append(mock_frames[query])
        
        mock_reader.read.side_effect = frame_sequence
        
        # Setup client with mocked connection
        client.reader = mock_reader
        client.writer = mock_writer
        
        # Call get_status_data
        result = await client.get_status_data()
        
        # Verify the result is a SystemStatus object
        assert isinstance(result, SystemStatus)
        assert result.system_mode == SystemMode.AUTO
        assert result.effective_mode == SystemMode.AUTO
        assert result.fan_mode == FanMode.AUTO
        assert result.all_mode is False
        assert result.outside_temp == 65  # From mock data
        assert result.zone1_humidity == 45
        assert result.fan_state == "On"
        assert result.compressor_stage_1 is False
        assert result.compressor_stage_2 is False
        assert result.aux_heat_stage_1 is False
        assert result.aux_heat_stage_2 is False
        assert result.humidify is False
        assert result.dehumidify is False
        assert result.reversing_valve is False
        assert result.raw is None
        assert len(result.zones) == 4
        
        # Verify zone data
        zone = result.zones[0]
        assert zone.zone_id == 1
        assert zone.cool_setpoint == 74
        assert zone.heat_setpoint == 68
        assert zone.temperature == 72
        assert zone.damper_position == 100  # 15/15 * 100

    @pytest.mark.asyncio
    async def test_get_status_data_with_raw(self, client, mock_reader, mock_writer):
        """Ensure include_raw=True returns base64 blob."""
        mock_frames = self.create_status_mock_data()
        frame_sequence = []
        for query in [
            "9.9.3",
            "9.9.4",
            "9.9.5",
            "1.1.9",
            "1.1.12",
            "1.1.16",
            "1.1.17",
            "1.1.18",
            "1.1.24",
        ]:
            frame_sequence.append(mock_frames[query])

        mock_reader.read.side_effect = frame_sequence
        client.reader = mock_reader
        client.writer = mock_writer

        result = await client.get_status_data(include_raw=True)

        assert isinstance(result.raw, str)
        assert len(result.raw) > 0

    @pytest.mark.asyncio
    async def test_set_zone_setpoints(self, client, mock_reader, mock_writer):
        """Test zone setpoint modification with read-modify-write pattern."""
        # Mock the initial read frames for rows 1.12 and 1.16
        row12_data = [0, 1, 12, 0, 2, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        row16_data = [0, 1, 16, 0, 0, 0, 74, 74, 74, 74, 0, 68, 68, 68, 68, 0, 0, 0, 0]
        
        row12_frame = self.create_mock_frame_data(99, 1, Function.reply, row12_data)
        row16_frame = self.create_mock_frame_data(99, 1, Function.reply, row16_data)
        
        # Mock OK replies for write operations
        ok_reply = self.create_mock_frame_data(99, 1, Function.reply, [0])
        
        # Setup mock reader to return frames in sequence
        mock_reader.read.side_effect = [row12_frame, row16_frame, ok_reply, ok_reply]
        
        # Setup client with mocked connection
        client.reader = mock_reader
        client.writer = mock_writer
        
        # Call set_zone_setpoints
        await client.set_zone_setpoints(
            zones=[1, 2],
            heat_setpoint=70,
            cool_setpoint=76,
            temporary_hold=True
        )
        
        # Verify write calls were made
        assert mock_writer.write.call_count == 4  # 2 reads + 2 writes
        
        # Verify the write data contains modified setpoints
        write_calls = [call[0][0] for call in mock_writer.write.call_args_list]
        
        # Check that writes were made (exact frame validation would require frame parsing)
        assert len(write_calls) == 4
        assert all(len(call) > 10 for call in write_calls)  # All should be valid frames

    @pytest.mark.asyncio
    async def test_set_system_mode(self, client, mock_reader, mock_writer):
        """Test system mode setting."""
        # Mock the initial read frame for row 1.12
        row12_data = [0, 1, 12, 0, 2, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        row12_frame = self.create_mock_frame_data(99, 1, Function.reply, row12_data)
        
        # Mock OK reply
        ok_reply = self.create_mock_frame_data(99, 1, Function.reply, [0])
        
        mock_reader.read.side_effect = [row12_frame, ok_reply]
        
        client.reader = mock_reader
        client.writer = mock_writer
        
        await client.set_system_mode(SystemMode.HEAT, True)
        
        # Verify read and write calls
        assert mock_writer.write.call_count == 2  # 1 read + 1 write
        
    @pytest.mark.asyncio
    async def test_set_fan_mode(self, client, mock_reader, mock_writer):
        """Test fan mode setting."""
        # Mock the initial read frame for row 1.17
        row17_data = [0, 1, 17, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        row17_frame = self.create_mock_frame_data(99, 1, Function.reply, row17_data)
        
        # Mock OK reply
        ok_reply = self.create_mock_frame_data(99, 1, Function.reply, [0])
        
        mock_reader.read.side_effect = [row17_frame, ok_reply]
        
        client.reader = mock_reader
        client.writer = mock_writer
        
        await client.set_fan_mode(FanMode.ON)
        
        # Verify read and write calls
        assert mock_writer.write.call_count == 2  # 1 read + 1 write

    @pytest.mark.asyncio
    async def test_send_with_reply_wrong_destination(self, client, mock_reader, mock_writer):
        """Test send_with_reply with wrong destination in reply."""
        # Mock frame with wrong destination (should be 99, but we'll use 1)
        wrong_dest_frame = self.create_mock_frame_data(1, 1, Function.reply, [0, 1, 16, 42])
        
        # Setup mock to return wrong destination 5 times (the retry limit)
        mock_reader.read.side_effect = [wrong_dest_frame] * 6
        
        client.reader = mock_reader
        client.writer = mock_writer
        
        # Should raise TimeoutError after retries
        with pytest.raises(TimeoutError, match="No valid reply received"):
            await client.send_with_reply(1, Function.read, [0, 1, 16])

    @pytest.mark.asyncio
    async def test_send_with_reply_error_response(self, client, mock_reader, mock_writer):
        """Test send_with_reply with error response."""
        # Mock error frame
        error_frame = self.create_mock_frame_data(99, 1, Function.error, [5])  # Some error code
        
        mock_reader.read.return_value = error_frame
        
        client.reader = mock_reader
        client.writer = mock_writer
        
        # Should raise OSError with error message
        with pytest.raises(OSError, match="Error reply received"):
            await client.send_with_reply(1, Function.read, [0, 1, 16])

    @pytest.mark.asyncio
    async def test_send_with_reply_connection_error(self, client, mock_reader, mock_writer):
        """Test send_with_reply with connection error during read."""
        # Mock connection error
        mock_reader.read.side_effect = ConnectionAbortedError("Connection lost")
        
        client.reader = mock_reader
        client.writer = mock_writer
        
        # Should raise RetryError after exhausting retries
        with pytest.raises(RetryError):
            await client.send_with_reply(1, Function.read, [0, 1, 16])

    @pytest.mark.asyncio
    async def test_read_row(self, client, mock_reader, mock_writer):
        """Test read_row method."""
        # Mock valid reply frame
        reply_data = [0, 1, 16, 74, 74, 74, 74]
        reply_frame = self.create_mock_frame_data(99, 1, Function.reply, reply_data)
        
        mock_reader.read.return_value = reply_frame
        
        client.reader = mock_reader
        client.writer = mock_writer
        
        result = await client.read_row(1, 1, 16)
        
        # Verify the call was made and result is returned
        mock_writer.write.assert_called_once()
        assert result.destination == 99
        assert result.source == 1
        assert result.function == Function.reply

    @pytest.mark.asyncio
    async def test_write_row_success(self, client, mock_reader, mock_writer):
        """Test successful write_row operation."""
        # Mock OK reply
        ok_reply = self.create_mock_frame_data(99, 1, Function.reply, [0])
        
        mock_reader.read.return_value = ok_reply
        
        client.reader = mock_reader
        client.writer = mock_writer
        
        # Should not raise any exception
        await client.write_row(1, 1, 16, [74, 74, 74, 74])
        
        mock_writer.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_row_failure(self, client, mock_reader, mock_writer):
        """Test write_row with error response."""
        # Mock error reply (non-zero first byte)
        error_reply = self.create_mock_frame_data(99, 1, Function.reply, [1])  # Error code 1
        
        mock_reader.read.return_value = error_reply
        
        client.reader = mock_reader
        client.writer = mock_writer
        
        # Should raise OSError
        with pytest.raises(OSError, match="Write failed with reply code 1"):
            await client.write_row(1, 1, 16, [74, 74, 74, 74])

    @pytest.mark.asyncio
    async def test_context_manager(self, client, mock_reader, mock_writer):
        """Test client as async context manager."""
        with patch('asyncio.open_connection', return_value=(mock_reader, mock_writer)):
            async with client:
                assert client.is_connected()
            
            # Should be closed after context exit
            mock_writer.close.assert_called_once()
            mock_writer.wait_closed.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_not_established_error(self, client):
        """Test operations without established connection."""
        # Try to read without connection
        with pytest.raises(ConnectionError, match="Not connected"):
            await client._read_data(10)
        
        # Try to write without connection
        with pytest.raises(ConnectionError, match="Not connected"):
            await client._write_data(b"test")

    @pytest.mark.asyncio
    async def test_get_frame_parsing(self, client, mock_reader, mock_writer):
        """Test frame parsing from buffer."""
        # Create a valid frame
        valid_frame = self.create_mock_frame_data(99, 1, Function.reply, [0, 1, 16, 74])
        
        # Add some invalid data before the valid frame
        invalid_data = b'\x00\x00\x00'
        full_data = invalid_data + valid_frame
        
        mock_reader.read.return_value = full_data
        
        client.reader = mock_reader
        client.writer = mock_writer
        
        result = await client.get_frame()
        
        # Verify we got a valid frame
        assert result.destination == 99
        assert result.source == 1
        assert result.function == Function.reply

    def test_is_serial_detection(self):
        """Test serial vs TCP connection detection."""
        tcp_client = ComfortZoneIIClient("localhost:8080", 4, 99)
        serial_client = ComfortZoneIIClient("/dev/ttyUSB0", 4, 99)
        
        assert not tcp_client._is_serial
        assert serial_client._is_serial
