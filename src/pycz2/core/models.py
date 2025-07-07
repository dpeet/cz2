# src/pycz2/core/models.py

from pydantic import BaseModel, Field

from .constants import FanMode, SystemMode


class ZoneStatus(BaseModel):
    zone_id: int
    temperature: int
    damper_position: int
    cool_setpoint: int
    heat_setpoint: int
    temporary: bool
    hold: bool
    out: bool


class SystemStatus(BaseModel):
    system_time: str
    system_mode: SystemMode
    effective_mode: SystemMode
    fan_mode: FanMode
    fan_state: str
    active_state: str
    all_mode: bool
    outside_temp: int
    air_handler_temp: int
    zone1_humidity: int
    zones: list[ZoneStatus]


# --- API Argument Models ---


class ZoneTemperatureArgs(BaseModel):
    heat: int | None = Field(None, ge=45, le=74)
    cool: int | None = Field(None, ge=64, le=99)
    temp: bool | None = False
    hold: bool | None = False
    out: bool | None = False


class SystemModeArgs(BaseModel):
    mode: SystemMode
    all: bool | None = None


class SystemFanArgs(BaseModel):
    fan: FanMode


class ZoneHoldArgs(BaseModel):
    hold: bool | None = None
    temp: bool | None = None
