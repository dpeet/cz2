# src/pycz2/core/frame.py
from typing import Any

from construct import (
    Array,
    Byte,
    Computed,
    Const,
    Enum,
    GreedyBytes,
    Int16ub,
    Padded,
    Peek,
    Pointer,
    Struct,
    this,
)
from crc import Calculator, Configuration

from .constants import Function

# CRC-16/CCITT-FALSE as used by the original Perl Digest::CRC
# polynomial: 0x1021, init: 0xFFFF, xor_out: 0x0000, reverse: False
CRC_CONFIG = Configuration(16, 0x1021, 0xFFFF, 0x0000, False, False)
CRC_CALCULATOR = Calculator(CRC_CONFIG)


def Crc16Ccitt(data: bytes) -> int:
    return CRC_CALCULATOR.checksum(data)


# The structure for testing if a slice of buffer contains a valid frame
# It peeks at the length, reads the whole potential frame, and validates the CRC
FrameTestStruct = Struct(
    "length" / Peek(Pointer(4, Byte)),
    "frame" / Peek(Padded(this.length + 10, GreedyBytes)),
    "valid" / Computed(lambda ctx: Crc16Ccitt(ctx.frame) == 0),
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
    # Just read the checksum value, validation happens separately
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
    return bytes(payload + checksum.to_bytes(2, "big"))
