# src/pycz2/config.py
import logging.config
from pathlib import Path

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Connection Settings
    CZ_CONNECT: str = "localhost:8899"
    CZ_ZONES: int = Field(default=1, ge=1, le=8)
    CZ_ZONE_NAMES: list[str] | None = None
    CZ_ID: int = Field(default=99, ge=1, le=255)

    # API Server Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # MQTT Settings
    MQTT_ENABLED: bool = False
    MQTT_HOST: str = "localhost"
    MQTT_PORT: int = 1883
    MQTT_USER: str | None = None
    MQTT_PASSWORD: str | None = None
    MQTT_TOPIC_PREFIX: str = "hvac/cz2"
    MQTT_PUBLISH_INTERVAL: int = Field(default=60, ge=5)

    # Cache Settings
    ENABLE_CACHE: bool = True
    CACHE_STALE_SECONDS: int = Field(default=300, ge=10)
    CACHE_DB_PATH: str | None = None  # Defaults to ~/.pycz2_cache.db

    # Service Settings (CLI-style refresh)
    CACHE_REFRESH_INTERVAL: int = Field(default=300, ge=30)  # Background refresh interval in seconds
    CACHE_MAX_AGE: int = Field(default=600, ge=60)  # Maximum cache age before forced refresh

    # Worker Settings (being phased out)
    WORKER_ENABLED: bool = False  # Disabled by default - using CLI-style service instead
    WORKER_POLL_INTERVAL: int = Field(default=30, ge=5)
    WORKER_RECONNECT_DELAY: int = Field(default=5, ge=1)
    WORKER_MAX_RECONNECT_DELAY: int = Field(default=300, ge=60)  # 5 minutes

    # SSE Settings
    ENABLE_SSE: bool = True
    SSE_HEARTBEAT_INTERVAL: int = Field(default=30, ge=10)
    SSE_MAX_SUBSCRIBERS_PER_IP: int = Field(default=5, ge=1)

    # Command Queue Settings
    COMMAND_QUEUE_MAX_SIZE: int = Field(default=100, ge=10)
    COMMAND_TIMEOUT_SECONDS: int = Field(default=30, ge=5)
    LOG_FILE_PATH: str = "~/.cache/pycz2/pycz2.log"

    @field_validator("CZ_ZONE_NAMES", mode="before")
    @classmethod
    def split_zone_names(cls, v: str | list[str] | None) -> list[str] | None:
        if isinstance(v, str):
            return [name.strip() for name in v.split(",") if name.strip()]
        return v

    @field_validator("CZ_ZONE_NAMES")
    @classmethod
    def validate_zone_names_count(cls, v: list[str] | None, info: ValidationInfo) -> list[str] | None:
        if v is not None and "CZ_ZONES" in info.data:
            if len(v) != info.data["CZ_ZONES"]:
                raise ValueError(
                    f"Number of zone names ({len(v)}) must match CZ_ZONES "
                    f"({info.data['CZ_ZONES']})."
                )
        return v


settings = Settings()

LOG_FILE_PATH = Path(settings.LOG_FILE_PATH).expanduser()
LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

# Basic logging configuration
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(levelprefix)s %(asctime)s [%(name)s] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "file": {
            "formatter": "default",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_FILE_PATH),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "encoding": "utf-8",
        },
    },
    "loggers": {
        "pycz2": {"handlers": ["default", "file"], "level": "INFO"},
        "uvicorn.error": {"handlers": ["default", "file"], "level": "INFO"},
        "uvicorn.access": {
            "handlers": ["default", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
