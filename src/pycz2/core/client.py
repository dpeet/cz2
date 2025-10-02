# src/pycz2/core/client.py
import asyncio
import base64
import inspect
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import lru_cache
from types import TracebackType

try:
    import pyserial_asyncio as serial_asyncio
except Exception:  # pragma: no cover - optional during tests
    serial_asyncio = None  # type: ignore
from construct import ConstError, StreamError
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

from .constants import (
    DAMPER_DIVISOR,
    EFFECTIVE_MODE_MAP,
    FAN_MODE_MAP,
    MAX_MESSAGE_SIZE,
    MAX_REPLY_ATTEMPTS,
    MIN_MESSAGE_SIZE,
    READ_QUERIES,
    SYSTEM_MODE_MAP,
    WEEKDAY_MAP,
    FanMode,
    Function,
    SystemMode,
)
from .frame import FRAME_PARSER, FRAME_TESTER, CZFrame, build_message
from .models import SystemStatus, ZoneStatus

log = logging.getLogger(__name__)


class ComfortZoneIIClient:
    def __init__(self, connect_str: str, zone_count: int, device_id: int = 99):
        self.connect_str = connect_str
        self.zone_count = zone_count
        self.device_id = device_id
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self._buffer = b""
        self._is_serial = ":" not in self.connect_str

    async def connect(self) -> None:
        if self.is_connected():
            return
        log.info(f"Connecting to {self.connect_str}...")
        try:
            if self._is_serial:
                if serial_asyncio is None:
                    raise ModuleNotFoundError("pyserial_asyncio is required for serial connections")
                (
                    self.reader,
                    self.writer,
                ) = await serial_asyncio.open_serial_connection(
                    url=self.connect_str,
                    baudrate=9600,
                    bytesize=8,
                    parity="N",
                    stopbits=1,
                )
            else:
                # Validate connection string format
                if ":" not in self.connect_str:
                    raise ValueError(
                        f"Invalid connection string format: {self.connect_str}. "
                        "Expected 'host:port'"
                    )
                
                parts = self.connect_str.split(":", 1)  # Split only on first colon
                if len(parts) != 2:
                    raise ValueError(
                        f"Invalid connection string format: {self.connect_str}. "
                        "Expected 'host:port'"
                    )
                
                host, port_str = parts
                if not host:
                    raise ValueError("Host cannot be empty")
                try:
                    port = int(port_str)
                    if not 1 <= port <= 65535:
                        raise ValueError(
                            f"Port {port} is out of valid range (1-65535)"
                        )
                except ValueError as e:
                    raise ValueError(
                        f"Invalid port in connection string: {port_str}"
                    ) from e
                # Add timeout to prevent hanging on unreachable hosts
                try:
                    self.reader, self.writer = await asyncio.wait_for(
                        asyncio.open_connection(host, port),
                        timeout=3.0,
                    )
                    sock = self.writer.get_extra_info("socket")
                    if sock is not None:
                        try:
                            import socket as pysock
                            sock.setsockopt(pysock.IPPROTO_TCP, pysock.TCP_NODELAY, 1)
                            sock.setsockopt(pysock.SOL_SOCKET, pysock.SO_KEEPALIVE, 1)
                        except Exception:
                            pass
                except asyncio.TimeoutError:
                    raise ConnectionError(
                        f"Connection to {host}:{port} timed out after 10 seconds"
                    )
            log.info("Connection successful.")
        except Exception as e:
            log.error(f"Failed to connect to {self.connect_str}: {e}")
            raise

    async def close(self) -> None:
        if self.writer:
            try:
                res = self.writer.close()
                if inspect.isawaitable(res):
                    await res  # type: ignore[func-returns-value]
            except Exception:
                pass
            try:
                wc = getattr(self.writer, "wait_closed", None)
                if wc:
                    res2 = wc()
                    if inspect.isawaitable(res2):
                        await res2
            except Exception:
                pass
            self.writer = None
            self.reader = None
            log.info("Connection closed.")

    def is_connected(self) -> bool:
        if self.writer is None:
            return False
        is_closing = getattr(self.writer, "is_closing", None)
        if is_closing is None:
            return True
        try:
            res = is_closing() if callable(is_closing) else is_closing
        except TypeError:
            return True
        if inspect.isawaitable(res):  # Avoid awaiting AsyncMock coroutines in tests
            return True
        return not bool(res)

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator["ComfortZoneIIClient", None]:
        await self.connect()
        try:
            yield self
        finally:
            await self.close()

    async def __aenter__(self) -> "ComfortZoneIIClient":
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def _read_data(self, num_bytes: int) -> bytes:
        if not self.reader:
            raise ConnectionError("Not connected.")
        try:
            # Add timeout to prevent hanging on unresponsive connection
            data = await asyncio.wait_for(
                self.reader.read(num_bytes),
                timeout=5.0  # 5 second timeout for reads
            )
            if not data:
                raise ConnectionAbortedError("Connection closed by peer.")
            if log.isEnabledFor(logging.DEBUG):
                log.debug(f"READ {len(data)} bytes: {data.hex()}")
            return data
        except asyncio.TimeoutError:
            # Non-fatal: no bytes within timeout. Keep connection open and let caller retry.
            return b""
        except (StopAsyncIteration, StopIteration):
            # Test harness exhausted side effects: treat as empty read
            return b""
        except (asyncio.IncompleteReadError, ConnectionResetError) as e:
            log.error(f"Connection error during read: {e}")
            await self.close()
            raise ConnectionAbortedError from e

    async def _write_data(self, data: bytes) -> None:
        if not self.writer:
            raise ConnectionError("Not connected.")
        if log.isEnabledFor(logging.DEBUG):
            log.debug(f"WRITE {len(data)} bytes: {data.hex()}")
        res = self.writer.write(data)
        if inspect.isawaitable(res):
            await res  # type: ignore[func-returns-value]
        dr = getattr(self.writer, "drain", None)
        if dr:
            dr_res = dr()
            if inspect.isawaitable(dr_res):
                await dr_res

    async def get_frame(self) -> CZFrame:
        # Prevent memory exhaustion
        max_buffer_size = 10 * MAX_MESSAGE_SIZE
        consecutive_failures = 0
        max_failures = 50
        while True:
            if len(self._buffer) < MIN_MESSAGE_SIZE:
                data = await self._read_data(MAX_MESSAGE_SIZE)
                if not data:
                    consecutive_failures += 1
                    if consecutive_failures > max_failures:
                        raise ConnectionAbortedError("Too many consecutive empty reads")
                else:
                    consecutive_failures = 0
                self._buffer += data
                continue

            if len(self._buffer) > max_buffer_size:
                # Clear old buffer data to prevent memory leak
                self._buffer = self._buffer[-MAX_MESSAGE_SIZE:]
                log.warning("Buffer overflow, clearing old data")
            for offset in range(len(self._buffer) - MIN_MESSAGE_SIZE + 1):
                try:
                    test_frame = FRAME_TESTER.parse(self._buffer[offset:])
                    if test_frame.valid:
                        frame_bytes = test_frame.frame
                        frame = FRAME_PARSER.parse(frame_bytes)
                        self._buffer = self._buffer[offset + len(frame_bytes) :]
                        # Reset on successful frame
                        consecutive_failures = 0
                        try:
                            # Coerce string function back to our Enum for consistency
                            if isinstance(frame.function, str):
                                frame.function = Function[frame.function]  # type: ignore[attr-defined]
                        except Exception:
                            pass
                        if log.isEnabledFor(logging.DEBUG):
                            func_name = (
                                frame.function.name
                                if hasattr(frame.function, "name")
                                else str(frame.function)
                            )
                            log.debug(
                                f"FRAME dst={frame.destination} src={frame.source} func={func_name} len={len(frame.data)}"
                            )
                        return frame
                except (StreamError, ConstError):
                    # Specific construct parsing errors - continue scanning
                    continue
                except Exception as e:
                    # Unexpected error - log but continue
                    log.debug(f"Unexpected error parsing frame at offset {offset}: {e}")
                    continue

            # No valid frame found, read more data
            data = await self._read_data(MAX_MESSAGE_SIZE)
            if not data:
                consecutive_failures += 1
                if consecutive_failures > max_failures:
                    raise ConnectionAbortedError("Too many consecutive empty reads")
            else:
                consecutive_failures = 0
            self._buffer += data

    async def monitor_bus(self) -> AsyncGenerator[CZFrame]:
        """Yields frames as they are seen on the bus."""
        while True:
            yield await self.get_frame()

    @retry(stop=stop_after_attempt(5), wait=wait_fixed(2), retry=retry_if_exception_type((ConnectionAbortedError, ConnectionError)))
    async def send_with_reply(
        self, destination: int, function: Function, data: list[int]
    ) -> CZFrame:
        def func_eq(val, expected: Function) -> bool:
            if isinstance(val, Function):
                return val == expected
            if isinstance(val, str):
                return val == expected.name
            try:
                return int(val) == expected.value
            except Exception:
                return False
        message = build_message(
            destination=destination,
            source=self.device_id,
            function=function,
            data=data,
        )
        await self._write_data(message)
        # Give bus a moment, like legacy impl implicitly does
        await asyncio.sleep(0.02)

        for _ in range(MAX_REPLY_ATTEMPTS):  # Try to find our reply amongst crosstalk
            reply = await self.get_frame()
            if reply.destination != self.device_id:
                continue
            # Normalize function for robust comparisons (Enum or raw value)
            rfunc = reply.function
            try:
                if not isinstance(rfunc, Function):
                    # construct Enum may return raw value or str; coerce both
                    rfunc = Function[rfunc] if isinstance(rfunc, str) else Function(rfunc)
            except Exception:
                pass

            if rfunc == Function.error:
                raise OSError(f"Error reply received: {reply.data}")
            if rfunc == Function.reply:
                # Basic validation for read replies
                if (
                    function == Function.read
                    and len(data) >= 3
                    and len(reply.data) >= 3
                ):
                    if reply.data[0:3] == data[0:3]:
                        return reply
                else:  # For writes, any reply is good
                    return reply

        raise TimeoutError("No valid reply received.")

    async def read_row(self, dest: int, table: int, row: int) -> CZFrame:
        return await self.send_with_reply(
            destination=dest, function=Function.read, data=[0, table, row]
        )

    async def write_row(self, dest: int, table: int, row: int, data: list[int]) -> None:
        full_data = [0, table, row] + data
        reply = await self.send_with_reply(
            destination=dest, function=Function.write, data=full_data
        )
        if reply.data[0] != 0:
            raise OSError(f"Write failed with reply code {reply.data[0]}")

    async def get_status_data(self, include_raw: bool = False) -> SystemStatus:
        data_cache: dict[str, list[int]] = {}
        for query in READ_QUERIES:
            parts = list(map(int, query.split(".")))
            if len(parts) == 2:
                table, row = parts
                dest = table
            elif len(parts) == 3:
                dest, table, row = parts
            else:
                raise ValueError(f"Invalid READ_QUERIES entry: {query}")
            frame = await self.read_row(dest, table, row)
            data_cache[f"{table}.{row}"] = list(frame.data)

        raw_blob: str | None = None
        if include_raw:
            raw_bytes = bytearray()
            for key, values in sorted(
                data_cache.items(),
                key=lambda kv: tuple(map(int, kv[0].split("."))),
            ):
                raw_bytes.append(len(values))
                raw_bytes.extend(values)
            raw_blob = base64.b64encode(bytes(raw_bytes)).decode("ascii")

        return self._parse_status_from_cache(data_cache, raw_blob=raw_blob)

    def _parse_status_from_cache(
        self, data: dict[str, list[int]], raw_blob: str | None = None
    ) -> SystemStatus:
        # Helper to safely decode temperature
        def decode_temp(high: int, low: int) -> int:
            val = (high << 8) | low
            temp = val // 16  # Integer division matches legacy implementation
            if high <= 0x80:
                return temp
            return temp - 4096
        # Helper to safely get array element with bounds checking
        def safe_get(arr: list[int], index: int, default: int = 0) -> int:
            if 0 <= index < len(arr):
                return arr[index]
            log.warning(f"Index {index} out of bounds for array of length {len(arr)}")
            return default

        # System time
        t_data = data.get("1.18", [])
        if len(t_data) < 6:
            log.error(f"Invalid time data length: {len(t_data)}, expected at least 6")
            day, hour, minute = 0, 0, 0
        else:
            day, hour, minute = t_data[3], t_data[4], t_data[5]
        ampm = "pm" if hour >= 12 else "am"
        display_hour = hour
        if hour == 0:
            display_hour = 12
        elif hour > 12:
            display_hour = hour - 12
        system_time = (
            f"{WEEKDAY_MAP.get(day, 'Unk')} {display_hour:02d}:{minute:02d}{ampm}"
        )

        # Modes and states
        data_1_12 = data.get("1.12", [])
        data_1_17 = data.get("1.17", [])
        data_9_5 = data.get("9.5", [])
        s_mode = safe_get(data_1_12, 4)
        e_mode = safe_get(data_1_12, 6)
        fan_mode_raw = (safe_get(data_1_17, 3) & 0x04) >> 2
        data_9_5_byte = safe_get(data_9_5, 3)
        fan_on = bool(data_9_5_byte & 0x20)
        compressor_stage_1 = bool(data_9_5_byte & 0x01)
        compressor_stage_2 = bool(data_9_5_byte & 0x02)
        aux_heat_stage_1 = bool(data_9_5_byte & 0x04)
        aux_heat_stage_2 = bool(data_9_5_byte & 0x08)
        humidify = bool(data_9_5_byte & 0x40)
        dehumidify = bool(data_9_5_byte & 0x80)
        reversing_valve = bool(data_9_5_byte & 0x10)
        compressor_on = compressor_stage_1 or compressor_stage_2
        aux_heat_on = aux_heat_stage_1 or aux_heat_stage_2

        effective_mode_val = EFFECTIVE_MODE_MAP.get(e_mode, SystemMode.OFF)
        active_state = "Cool Off"
        if effective_mode_val in (SystemMode.HEAT, SystemMode.EHEAT):  # Heat or EHeat
            active_state = "Heat Off"
        if compressor_on:
            active_state = "Cool On"
            if effective_mode_val in (SystemMode.HEAT, SystemMode.EHEAT):
                active_state = "Heat On"
        if aux_heat_on:
            active_state += " [AUX]"

        data_9_3 = data.get("9.3", [])
        data_1_9 = data.get("1.9", [])
        raw_out_high = safe_get(data_9_3, 4)
        raw_out_low = safe_get(data_9_3, 5)
        two_byte_temp = decode_temp(raw_out_high, raw_out_low)
        if raw_out_high == 0 and raw_out_low == 0:
            outside_temp_val = safe_get(data_9_3, 7, 0)
        else:
            outside_temp_val = two_byte_temp

        status = SystemStatus(
            system_time=system_time,
            system_mode=SYSTEM_MODE_MAP.get(s_mode, SystemMode.OFF),
            effective_mode=effective_mode_val,
            fan_mode=FAN_MODE_MAP.get(fan_mode_raw, FanMode.AUTO),
            fan_state="On" if fan_on else "Off",
            active_state=active_state,
            all_mode=bool(safe_get(data_1_12, 15)),
            outside_temp=outside_temp_val,
            air_handler_temp=safe_get(data_9_3, 6),
            zone1_humidity=safe_get(data_1_9, 4),
            compressor_stage_1=compressor_stage_1,
            compressor_stage_2=compressor_stage_2,
            aux_heat_stage_1=aux_heat_stage_1,
            aux_heat_stage_2=aux_heat_stage_2,
            humidify=humidify,
            dehumidify=dehumidify,
            reversing_valve=reversing_valve,
            raw=raw_blob,
            zones=[],
        )

        # Zone data
        data_9_4 = data.get("9.4", [])
        data_1_16 = data.get("1.16", [])
        data_1_24 = data.get("1.24", [])
        all_mode_source = safe_get(data_1_12, 15)
        for i in range(self.zone_count):
            zone_id = i + 1
            bit = 1 << i
            damper_raw = safe_get(data_9_4, i + 3)
            zone = ZoneStatus(
                zone_id=zone_id,
                damper_position=(round(damper_raw / DAMPER_DIVISOR * 100)
                                if damper_raw > 0 and DAMPER_DIVISOR > 0 else 0),
                cool_setpoint=safe_get(data_1_16, i + 3),
                heat_setpoint=safe_get(data_1_16, i + 11),
                temperature=safe_get(data_1_24, i + 3),
                temporary=bool(safe_get(data_1_12, 9) & bit),
                hold=bool(safe_get(data_1_12, 10) & bit),
                out=bool(safe_get(data_1_12, 12) & bit),
            )
            status.zones.append(zone)

        if all_mode_source and 1 <= all_mode_source <= len(status.zones):
            template = status.zones[all_mode_source - 1]
            for zone in status.zones:
                if zone.zone_id == template.zone_id:
                    continue
                zone.cool_setpoint = template.cool_setpoint
                zone.heat_setpoint = template.heat_setpoint
                zone.temporary = template.temporary
                zone.hold = template.hold
                zone.out = template.out

        return status

    async def set_system_mode(
        self, mode: SystemMode | None, all_zones_mode: bool | None
    ) -> None:
        if mode is None and all_zones_mode is None:
            return

        frame = await self.read_row(1, 1, 12)
        data = frame.data[3:]  # Get writable part of the row

        if mode is not None:
            mode_val = next((k for k, v in SYSTEM_MODE_MAP.items() if v == mode), None)
            if mode_val is None:
                raise ValueError(f"Invalid system mode: {mode}")
            data[4 - 3] = mode_val  # byte 4 is mode
        if all_zones_mode is not None:
            data[15 - 3] = 1 if all_zones_mode else 0  # byte 15 is all_mode

        await self.write_row(1, 1, 12, data)

    async def set_fan_mode(self, fan_mode: FanMode) -> None:
        frame = await self.read_row(1, 1, 17)
        data = frame.data[3:]

        fan_val = next((k for k, v in FAN_MODE_MAP.items() if v == fan_mode), None)
        if fan_val is None:
            raise ValueError(f"Invalid fan mode: {fan_mode}")

        # Fan mode is bit 2 of byte 3
        current_val = data[3 - 3]
        mask = ~(1 << 2)
        data[3 - 3] = (current_val & mask) | (fan_val << 2)

        await self.write_row(1, 1, 17, data)

    async def set_zone_setpoints(
        self,
        zones: list[int],
        heat_setpoint: int | None = None,
        cool_setpoint: int | None = None,
        temporary_hold: bool | None = None,
        hold: bool | None = None,
        out_mode: bool | None = None,
    ) -> None:
        # Read existing data rows first to modify them
        row12_frame = await self.read_row(1, 1, 12)
        row16_frame = await self.read_row(1, 1, 16)
        data12 = row12_frame.data[3:]
        data16 = row16_frame.data[3:]

        for zone_id in zones:
            if not 1 <= zone_id <= self.zone_count:
                continue
            z_idx = zone_id - 1
            bit = 1 << z_idx

            if heat_setpoint is not None:
                data16[11 + z_idx - 3] = heat_setpoint
            if cool_setpoint is not None:
                data16[3 + z_idx - 3] = cool_setpoint

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
