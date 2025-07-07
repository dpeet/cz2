# src/pycz2/core/constants.py
from enum import Enum

# Protocol constants
PROTOCOL_SIZE = 10
MIN_MESSAGE_SIZE = PROTOCOL_SIZE + 1
MAX_MESSAGE_SIZE = PROTOCOL_SIZE + 255


# Function codes
class Function(Enum):
    reply = 0x06
    read = 0x0B
    write = 0x0C
    error = 0x15


# System modes
class SystemMode(str, Enum):
    HEAT = "Heat"
    COOL = "Cool"
    AUTO = "Auto"
    EHEAT = "EHeat"
    OFF = "Off"


# Fan modes
class FanMode(str, Enum):
    AUTO = "Auto"
    ON = "On"


# Mappings from raw values to enums
SYSTEM_MODE_MAP = {
    0: SystemMode.HEAT,
    1: SystemMode.COOL,
    2: SystemMode.AUTO,
    3: SystemMode.EHEAT,
    4: SystemMode.OFF,
}

EFFECTIVE_MODE_MAP = SYSTEM_MODE_MAP

FAN_MODE_MAP = {
    0: FanMode.AUTO,
    1: FanMode.ON,
}

WEEKDAY_MAP = {0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat"}

# The set of queries needed to build a full status report
READ_QUERIES = [
    "9.3",
    "9.4",
    "9.5",  # Panel data
    "1.9",
    "1.12",
    "1.16",
    "1.17",
    "1.18",
    "1.24",  # Master controller data
]

# Damper position calculation divisor
DAMPER_DIVISOR = 15.0
assert DAMPER_DIVISOR > 0, "Damper divisor must be positive"

# Maximum attempts to find a reply frame amongst bus crosstalk
MAX_REPLY_ATTEMPTS = 5
