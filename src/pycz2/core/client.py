# src/pycz2/core/client.py
import asyncio
import logging
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import AsyncGenerator, List, Optional

import pyserial_asyncio
from tenacity import retry, stop_after_attempt, wait_fixed, RetryError

from .constants import (
    MAX_MESSAGE_SIZE,
    MIN_MESSAGE_SIZE,
    Function,
    SystemMode,
    FanMode,
    SYSTEM_MODE_MAP,
    EFFECTIVE_MODE_MAP,
    FAN_MODE_MAP,
    WEEKDAY_MAP,
    READ_QUERIES,
)
from .frame import CZFrame, FRAME_PARSER, FRAME_TESTER, build_message
from .models import SystemStatus, ZoneStatus

log = logging.getLogger(__name__)


class ComfortZoneIIClient:
    def __init__(self, connect_str: str, zone_count: int, device_id: int = 99):
        self.connect_str = connect_str
        self.zone_count = zone_count
        self.device_id = device_id
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self._buffer = b""
        self._is_serial = not (":" in self.connect_str)

    async def connect(self):
        if self.is_connected():
            return
        log.info(f"Connecting to {self.connect_str}...")
        try:
            if self._is_serial:
                self.reader, self.writer = await pyserial_asyncio.open_serial_connection(
                    url=self.connect_str, baudrate=9600, bytesize=8, parity="N", stopbits=1
                )
            else:
                host, port = self.connect_str.split(":")
                self.reader, self.writer = await asyncio.open_connection(host, int(port))
            log.info("Connection successful.")
        except Exception as e:
            log.error(f"Failed to connect to {self.connect_str}: {e}")
            raise

    async def close(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
            self.writer = None
            self.reader = None
            log.info("Connection closed.")

    def is_connected(self) -> bool:
        return self.writer is not None and not self.writer.is_closing()

    @asynccontextmanager
    async def connection(self):
        await self.connect()
        try:
            yield
        finally:
            await self.close()

    __aenter__ = connection
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _read_data(self, num_bytes: int) -> bytes:
        if not self.reader:
            raise ConnectionError("Not connected.")
        try:
            data = await self.reader.read(num_bytes)
            if not data:
                raise ConnectionAbortedError("Connection closed by peer.")
            return data
        except (asyncio.IncompleteReadError, ConnectionResetError) as e:
            log.error(f"Connection error during read: {e}")
            await self.close()
            raise ConnectionAbortedError from e

    async def _write_data(self, data: bytes):
        if not self.writer:
            raise ConnectionError("Not connected.")
        self.writer.write(data)
        await self.writer.drain()

    async def get_frame(self) -> CZFrame:
        while True:
            if len(self._buffer) < MIN_MESSAGE_SIZE:
                self._buffer += await self._read_data(MAX_MESSAGE_SIZE)
                continue

            for offset in range(len(self._buffer) - MIN_MESSAGE_SIZE + 1):
                try:
                    test_frame = FRAME_TESTER.parse(self._buffer[offset:])
                    if test_frame.valid:
                        frame_bytes = test_frame.frame
                        frame = FRAME_PARSER.parse(frame_bytes)
                        self._buffer = self._buffer[offset + len(frame_bytes) :]
                        return frame
                except Exception:
                    continue  # Ignore parsing errors and keep scanning

            # No valid frame found, read more data
            self._buffer += await self._read_data(MAX_MESSAGE_SIZE)

    async def monitor_bus(self) -> AsyncGenerator[CZFrame, None]:
        """Yields frames as they are seen on the bus."""
        while True:
            yield await self.get_frame()

    @retry(stop=stop_after_attempt(5), wait=wait_fixed(2))
    async def send_with_reply(
        self, destination: int, function: Function, data: List[int]
    ) -> CZFrame:
        message = build_message(
            destination=destination,
            source=self.device_id,
            function=function,
            data=data,
        )
        await self._write_data(message)

        for _ in range(5):  # Try to find our reply amongst crosstalk
            reply = await self.get_frame()
            if reply.destination != self.device_id:
                continue
            if reply.function == Function.error:
                raise IOError(f"Error reply received: {reply.data}")
            if reply.function == Function.reply:
                # Basic validation for read replies
                if function == Function.read and len(data) >= 3 and len(reply.data) >= 3:
                    if reply.data[0:3] == data[0:3]:
                        return reply
                else: # For writes, any reply is good
                    return reply

        raise asyncio.TimeoutError("No valid reply received.")

    async def read_row(self, dest: int, table: int, row: int) -> CZFrame:
        return await self.send_with_reply(
            destination=dest, function=Function.read, data=[0, table, row]
        )

    async def write_row(self, dest: int, table: int, row: int, data: List[int]):
        full_data = [0, table, row] + data
        reply = await self.send_with_reply(
            destination=dest, function=Function.write, data=full_data
        )
        if reply.data[0] != 0:
            raise IOError(f"Write failed with reply code {reply.data[0]}")

    async def get_status_data(self) -> SystemStatus:
        data_cache = {}
        for query in READ_QUERIES:
            dest, table, row = map(int, query.split("."))
            frame = await self.read_row(dest, table, row)
            data_cache[query] = frame.data

        return self._parse_status_from_cache(data_cache)

    def _parse_status_from_cache(self, data: dict) -> SystemStatus:
        # Helper to safely decode temperature
        def decode_temp(high: int, low: int) -> int:
            val = (high << 8) | low
            # Standard 16-bit two's complement, then divide by 16
            temp = (val - 65536) if val & 0x8000 else val
            return round(temp / 16.0)

        # System time
        t_data = data["1.18"]
        day, hour, minute = t_data[3], t_data[4], t_data[5]
        ampm = "pm" if hour >= 12 else "am"
        display_hour = hour
        if hour == 0:
            display_hour = 12
        elif hour > 12:
            display_hour = hour - 12
        system_time = f"{WEEKDAY_MAP.get(day, 'Unk')} {display_hour:02d}:{minute:02d}{ampm}"

        # Modes and states
        s_mode = data["1.12"][4]
        e_mode = data["1.12"][6]
        fan_mode_raw = (data["1.17"][3] & 0x04) >> 2
        fan_on = bool(data["9.5"][3] & 0x20)
        compressor_on = bool(data["9.5"][3] & 0x03)
        aux_heat_on = bool(data["9.5"][3] & 0x0C)

        active_state = "Cool Off"
        if e_mode in (SYSTEM_MODE_MAP.get(0), SYSTEM_MODE_MAP.get(3)): # Heat or EHeat
            active_state = "Heat Off"
        if compressor_on:
            active_state = "Cool On"
            if e_mode in (SYSTEM_MODE_MAP.get(0), SYSTEM_MODE_MAP.get(3)):
                active_state = "Heat On"
        if aux_heat_on:
            active_state += " [AUX]"


        status = SystemStatus(
            system_time=system_time,
            system_mode=SYSTEM_MODE_MAP.get(s_mode, SystemMode.OFF),
            effective_mode=EFFECTIVE_MODE_MAP.get(e_mode, SystemMode.OFF),
            fan_mode=FAN_MODE_MAP.get(fan_mode_raw, FanMode.AUTO),
            fan_state="On" if fan_on else "Off",
            active_state=active_state,
            all_mode=bool(data["1.12"][15]),
            outside_temp=decode_temp(data["9.3"][4], data["9.3"][5]),
            air_handler_temp=data["9.3"][6],
            zone1_humidity=data["1.9"][4],
            zones=[],
        )

        # Zone data
        for i in range(self.zone_count):
            zone_id = i + 1
            bit = 1 << i
            damper_raw = data["9.4"][i + 3]
            zone = ZoneStatus(
                zone_id=zone_id,
                damper_position=round(damper_raw / 15.0 * 100) if damper_raw > 0 else 0,
                cool_setpoint=data["1.16"][i + 3],
                heat_setpoint=data["1.16"][i + 11],
                temperature=data["1.24"][i + 3],
                temporary=bool(data["1.12"][9] & bit),
                hold=bool(data["1.12"][10] & bit),
                out=bool(data["1.12"][12] & bit),
            )
            status.zones.append(zone)

        return status

    async def set_system_mode(self, mode: Optional[SystemMode], all_zones_mode: Optional[bool]):
        if mode is None and all_zones_mode is None: return
        
        frame = await self.read_row(1, 1, 12)
        data = frame.data[3:] # Get writable part of the row
        
        if mode is not None:
            mode_val = next(k for k, v in SYSTEM_MODE_MAP.items() if v == mode)
            data[4-3] = mode_val # byte 4 is mode
        if all_zones_mode is not None:
            data[15-3] = 1 if all_zones_mode else 0 # byte 15 is all_mode
        
        await self.write_row(1, 1, 12, data)

    async def set_fan_mode(self, fan_mode: FanMode):
        frame = await self.read_row(1, 1, 17)
        data = frame.data[3:]
        
        fan_val = next(k for k, v in FAN_MODE_MAP.items() if v == fan_mode)
        
        # Fan mode is bit 2 of byte 3
        current_val = data[3-3]
        mask = ~(1 << 2)
        data[3-3] = (current_val & mask) | (fan_val << 2)
        
        await self.write_row(1, 1, 17, data)

    async def set_zone_setpoints(
        self,
        zones: List[int],
        heat_setpoint: Optional[int] = None,
        cool_setpoint: Optional[int] = None,
        temporary_hold: Optional[bool] = None,
        hold: Optional[bool] = None,
        out_mode: Optional[bool] = None,
    ):
        # Read existing data rows first to modify them
        row12_frame = await self.read_row(1, 1, 12)
        row16_frame = await self.read_row(1, 1, 16)
        data12 = row12_frame.data[3:]
        data16 = row16_frame.data[3:]

        for zone_id in zones:
            if not (1 <= zone_id <= self.zone_count): continue
            z_idx = zone_id - 1
            bit = 1 << z_idx

            if heat_setpoint is not None: data16[11 + z_idx - 3] = heat_setpoint
            if cool_setpoint is not None: data16[3 + z_idx - 3] = cool_setpoint
            
            if temporary_hold is not None:
                data12[9 - 3] = (data12[9 - 3] & ~bit) | (int(temporary_hold) << z_idx)
            if hold is not None:
                data12[10 - 3] = (data12[10 - 3] & ~bit) | (int(hold) << z_idx)
            if out_mode is not None:
                data12[12 - 3] = (data12[12 - 3] & ~bit) | (int(out_mode) << z_idx)

        await self.write_row(1, 1, 12, data12)
        await self.write_row(1, 1, 16, data16)


@lru_cache
def get_client() -> ComfortZoneIIClient:
    """Cached factory for the client."""
    from ..config import settings
    return ComfortZoneIIClient(
        connect_str=settings.CZ_CONNECT,
        zone_count=settings.CZ_ZONES,
        device_id=settings.CZ_ID,
    )

@lru_cache
def get_lock() -> asyncio.Lock:
    """A global lock to ensure sequential commands to the HVAC bus."""
    return asyncio.Lock()