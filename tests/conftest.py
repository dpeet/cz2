# tests/conftest.py
import os
import tempfile
import pytest

# Use a temporary database for tests to avoid polluting user's cache
test_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ.setdefault("CACHE_DB_PATH", test_db.name)

# Ensure test-friendly settings: disable background services to avoid hangs
os.environ.setdefault("ENABLE_SSE", "false")
os.environ.setdefault("WORKER_ENABLED", "false")
os.environ.setdefault("MQTT_ENABLED", "false")
os.environ.setdefault("ENABLE_CACHE", "true")

@pytest.fixture(autouse=True)
def _isolation_env(monkeypatch):
    # Also patch settings directly in case module already loaded
    try:
        from pycz2 import config as cfg
        monkeypatch.setattr(cfg.settings, "ENABLE_SSE", False, raising=False)
        monkeypatch.setattr(cfg.settings, "WORKER_ENABLED", False, raising=False)
        monkeypatch.setattr(cfg.settings, "MQTT_ENABLED", False, raising=False)
        monkeypatch.setattr(cfg.settings, "ENABLE_CACHE", True, raising=False)
    except Exception:
        pass
    yield
