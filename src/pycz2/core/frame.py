# src/pycz2/core/frame.py
from typing import Any

from construct import (
    Array,
    Byte,
    Bytes,
    Computed,
    Const,
    Enum,
    Peek,
    Pointer,
    Struct,
    this,
)
from crc import Calculator, Configuration
from construct import Int16ub

from .constants import Function

# CRC-16/IBM (ARC) to match Perl Digest::CRC default crc16
# polynomial: 0x8005, init: 0x0000, xor_out: 0x0000, reflect_in/out: True
CRC_CONFIG = Configuration(16, 0x8005, 0x0000, 0x0000, True, True)
CRC_CALCULATOR = Calculator(CRC_CONFIG)


def Crc16Ccitt(data: bytes) -> int:
    return CRC_CALCULATOR.checksum(data)


# The structure for testing if a slice of buffer contains a valid frame
# It peeks at the length, reads the whole potential frame, and validates the CRC
FrameTestStruct = Struct(
    "length" / Peek(Pointer(4, Byte)),
    # Read exactly length+10 bytes for CRC validation, mirroring Perl
    "frame" / Peek(Bytes(this.length + 10)),
    "valid"
    / Computed(
        lambda ctx: (ctx.length or 0) > 0 and Crc16Ccitt(ctx.frame) == 0
    ),
)

# The main structure for parsing a complete, valid frame
FrameStruct = Struct(
    "destination" / Byte,
    Const(b"\x00"),
    "source" / Byte,
    Const(b"\x00"),
    "length" / Byte,
    Const(b"\x00\x00"),
    "function"
    / Enum(Byte, **{f.name: f.value for f in Function}, default=Function.error),
    "data" / Array(this.length, Byte),
    # Read checksum as big-endian for testing convenience (CRC validation still uses whole frame)
    "checksum" / Int16ub,
)

# Combine the two for a single parsing object
# It first finds a valid frame using the tester, then parses it fully.
# Note: The * operator approach doesn't work in newer construct versions
# CZFrame would need to be implemented differently if needed

# Type alias for parsed frame
CZFrame = Any  # This represents the parsed frame structure from construct

# Alias for convenience
FRAME_TESTER = FrameTestStruct
FRAME_PARSER = FrameStruct


def build_message(
    destination: int, source: int, function: Function, data: list[int]
) -> bytes:
    """Builds a message frame to be sent over the wire."""
    header_data = {
        "destination": destination,
        "source": source,
        "length": len(data),
        "function": function.name,
    }
    # This is a bit of a hack since construct is mainly for parsing, but it works.
    # We build the header, then append the data and calculate the checksum.
    header = Struct(
        "destination" / Byte,
        Const(b"\x00"),
        "source" / Byte,
        Const(b"\x00"),
        "length" / Byte,
        Const(b"\x00\x00"),
        "function" / Enum(Byte, **{f.name: f.value for f in Function}),
    ).build(header_data)

    payload = header + bytes(data)
    checksum = Crc16Ccitt(payload)
    # Perl used pack("S", ...) which is native-endian (little-endian on x86)
    # The bus expects CRC bytes least-significant first.
    return bytes(payload + checksum.to_bytes(2, "little"))
