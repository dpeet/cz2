# tests/core/test_frame.py
from pycz2.core.constants import Function
from pycz2.core.frame import FRAME_PARSER, Crc16Ccitt, build_message


class TestBuildMessage:
    """Test cases for the build_message function."""

    def test_build_message_read_command(self) -> None:
        """Test building a READ command message with known inputs."""
        # Inputs
        destination = 9
        source = 99
        function = Function.read
        data = [1, 16]  # Table 1, Row 16

        # Build the message
        result = build_message(destination, source, function, data)

        # Expected frame structure:
        # destination (1), 0x00 (1), source (1), 0x00 (1), length (1), 0x00 0x00 (2),
        # function (1), data (2), checksum (2) = 12 bytes total
        assert len(result) == 12

        # Verify header bytes
        assert result[0] == 9  # destination
        assert result[1] == 0x00  # constant
        assert result[2] == 99  # source
        assert result[3] == 0x00  # constant
        assert result[4] == 2  # length (2 data bytes)
        assert result[5] == 0x00  # constant
        assert result[6] == 0x00  # constant
        assert result[7] == 0x0B  # Function.read value

        # Verify data bytes
        assert result[8] == 1  # table
        assert result[9] == 16  # row

        # Verify the CRC is correct (Crc16Ccitt of whole frame equals 0)
        assert Crc16Ccitt(result) == 0

    def test_build_message_write_command(self) -> None:
        """Test building a WRITE command message."""
        # Inputs
        destination = 1
        source = 99
        function = Function.write
        data = [1, 12, 4, 2]  # Table 1, Row 12, Byte 4, Value 2

        # Build the message
        result = build_message(destination, source, function, data)

        # Verify length
        assert len(result) == 14  # 10 header + 4 data + 2 checksum

        # Verify header
        assert result[0] == 1  # destination
        assert result[2] == 99  # source
        assert result[4] == 4  # length
        assert result[7] == 0x0C  # Function.write value

        # Verify data
        assert result[8:12] == bytes([1, 12, 4, 2])

        # Verify CRC
        assert Crc16Ccitt(result) == 0

    def test_build_message_reply(self) -> None:
        """Test building a REPLY message."""
        destination = 99
        source = 1
        function = Function.reply
        data = [0x06, 0x00]  # ACK reply

        result = build_message(destination, source, function, data)

        assert len(result) == 12
        assert result[0] == 99  # destination
        assert result[2] == 1  # source
        assert result[7] == 0x06  # Function.reply value
        assert result[8:10] == bytes([0x06, 0x00])
        assert Crc16Ccitt(result) == 0


class TestFrameParser:
    """Test cases for the FRAME_PARSER."""

    def test_parse_valid_read_frame(self) -> None:
        """Test parsing a known-valid READ command frame."""
        # This is a valid frame: destination=9, source=99, function=read, data=[1, 16]
        # Built using the build_message function to ensure it's valid
        raw_frame = build_message(9, 99, Function.read, [1, 16])

        # Parse the frame
        parsed = FRAME_PARSER.parse(raw_frame)
        assert parsed is not None  # Type guard for pyright

        # Verify all fields
        assert parsed.destination == 9
        assert parsed.source == 99
        assert parsed.function == "read"  # Enum returns the name as string
        assert list(parsed.data) == [1, 16]
        assert parsed.checksum == int.from_bytes(raw_frame[-2:], "big")

    def test_parse_valid_write_frame(self) -> None:
        """Test parsing a known-valid WRITE command frame."""
        # Build a write frame
        raw_frame = build_message(1, 99, Function.write, [1, 12, 4, 2])

        # Parse it
        parsed = FRAME_PARSER.parse(raw_frame)
        assert parsed is not None  # Type guard for pyright

        assert parsed.destination == 1
        assert parsed.source == 99
        assert parsed.function == "write"
        assert list(parsed.data) == [1, 12, 4, 2]

    def test_parse_reply_frame(self) -> None:
        """Test parsing a REPLY frame."""
        raw_frame = build_message(99, 1, Function.reply, [0x06, 0x00])

        parsed = FRAME_PARSER.parse(raw_frame)
        assert parsed is not None  # Type guard for pyright

        assert parsed.destination == 99
        assert parsed.source == 1
        assert parsed.function == "reply"
        assert list(parsed.data) == [0x06, 0x00]

    def test_parse_empty_data_frame(self) -> None:
        """Test parsing a frame with no data bytes."""
        raw_frame = build_message(1, 2, Function.error, [])

        parsed = FRAME_PARSER.parse(raw_frame)
        assert parsed is not None  # Type guard for pyright

        assert parsed.destination == 1
        assert parsed.source == 2
        assert parsed.function == "error"
        assert list(parsed.data) == []


class TestRoundTrip:
    """Test round-trip conversion between building and parsing."""

    def test_round_trip_various_messages(self) -> None:
        """Test that build_message and FRAME_PARSER are perfect inverses."""
        test_cases = [
            (9, 99, Function.read, [1, 16]),
            (1, 99, Function.write, [1, 12, 4, 2]),
            (99, 1, Function.reply, [0x06, 0x00]),
            (1, 2, Function.error, []),
            (255, 255, Function.read, list(range(10))),  # Larger data payload
        ]

        for dest, src, func, data in test_cases:
            # Build the message
            built = build_message(dest, src, func, data)

            # Parse it back
            parsed = FRAME_PARSER.parse(built)
            assert parsed is not None  # Type guard for pyright

            # Verify round-trip integrity
            assert parsed.destination == dest
            assert parsed.source == src
            assert parsed.function == func.name
            assert list(parsed.data) == data

            # Rebuild from parsed data and verify bytes match
            rebuilt = build_message(
                parsed.destination,
                parsed.source,
                Function[parsed.function],
                list(parsed.data),
            )
            assert rebuilt == built

    def test_round_trip_max_data_size(self) -> None:
        """Test round-trip with maximum data size (255 bytes)."""
        # Create a data payload of 255 bytes
        data = list(range(255))

        built = build_message(1, 2, Function.write, data)
        parsed = FRAME_PARSER.parse(built)
        assert parsed is not None  # Type guard for pyright

        assert parsed.destination == 1
        assert parsed.source == 2
        assert parsed.function == "write"
        assert list(parsed.data) == data
        assert len(parsed.data) == 255
