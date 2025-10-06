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
    compressor_stage_1: bool = False
    compressor_stage_2: bool = False
    aux_heat_stage_1: bool = False
    aux_heat_stage_2: bool = False
    humidify: bool = False
    dehumidify: bool = False
    reversing_valve: bool = False
    raw: str | None = None
    zones: list[ZoneStatus]

    def to_dict(self, include_raw: bool = False, flat: bool = False) -> dict:
        """
        Convert SystemStatus to dictionary.

        Args:
            include_raw: Include raw HVAC data blob
            flat: Apply legacy flat format transformations for backwards compatibility
        """
        import time as time_module

        exclude = None if include_raw else {"raw"}
        data = self.model_dump(exclude=exclude, exclude_none=True)

        if flat:
            # Parity Requirement 2: Convert all_mode boolean to numeric (0/1)
            # Integers 1-8 pass through unchanged (future-proof)
            if isinstance(data.get("all_mode"), bool):
                data["all_mode"] = 1 if data["all_mode"] else 0

            # Parity Requirement 3: Add time field (Unix timestamp)
            data["time"] = int(time_module.time())

            # Parity Requirement 4: Convert damper_position to string in all zones
            for zone in data.get("zones", []):
                if "damper_position" in zone:
                    zone["damper_position"] = str(zone["damper_position"])

        return data

    def to_json(self, include_raw: bool = False, flat: bool = False, **kwargs) -> str:
        """
        Convert SystemStatus to JSON string.

        Args:
            include_raw: Include raw HVAC data blob
            flat: Apply legacy flat format transformations for backwards compatibility
        """
        # Use to_dict for flat transformations, then serialize to JSON
        if flat:
            import json

            data = self.to_dict(include_raw=include_raw, flat=True)
            return json.dumps(data, **kwargs)
        else:
            exclude = None if include_raw else {"raw"}
            return self.model_dump_json(exclude=exclude, exclude_none=True, **kwargs)


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
