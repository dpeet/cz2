# Backend Code Review — March 7, 2026

Cross-validated review by Claude (Opus 4.6), Codex (GPT-5.4), and Gemini (3 Pro).
Focus: bugs, DRY/KISS violations, reliability of RS-485 thermostat communication.

**Status: All 21 findings resolved** (March 7, 2026).

## Summary

| Severity | Count | Resolved |
|----------|-------|----------|
| Critical | 3 | 3/3 |
| High | 5 | 5/5 |
| Medium | 5 | 5/5 |
| Low | 7 | 7/7 |

---

## Critical

### 1. Cache notification crashes when subscribers exist — RESOLVED

**File:** `cache.py:277-286`
**Reviewers:** All three

```python
async def _notify_subscribers(self) -> None:
    if not self._subscribers:
        return

        status = self._status or self.get_empty_status()  # DEAD CODE (after return)
    update = {
        "status": status.to_dict(),  # NameError: 'status' undefined
```

The `status = ...` line was indented inside the `if` block after `return` — it never
executed. When subscribers exist (the only case that matters), `status` was never
assigned, causing `NameError`. All cache subscriber notifications were broken.

**Fix applied:** Un-indented `status = self._status or self.get_empty_status()` to
method level. Added test in `tests/test_cache.py` confirming subscribers receive
updates.

---

### 2. Nested retry explosion — up to 31,250 seconds of blocking — RESOLVED

**Files:** `client.py:212,281`, `constants.py:69-75`
**Reviewers:** All three

Three nested retry layers multiplied:
- `get_frame()`: 50 empty reads × 5s each = 250s
- `send_with_reply()` inner: 5 sends × 5 frame reads = 25 × 250s
- Tenacity `@retry` decorator: 5 outer retries

**Fix applied:**
- Removed the Tenacity `@retry` decorator and `tenacity` dependency entirely
- Dropped `max_failures` in `get_frame` from 50 to 5
- Reduced `MAX_SEND_RETRIES` from 5 to 3
- Worst case now: 3 sends × 5 reads × 5s = 75s (bounded by `COMMAND_TIMEOUT_SECONDS`)

---

### 3. Timeout includes lock wait time (Bug #2 root cause) — RESOLVED

**File:** `hvac_service.py:117-184`
**Reviewers:** All three

`asyncio.wait_for()` wrapped the entire `_execute_with_lock()` including lock
acquisition. If a background refresh held the lock for 20s, a command only had
10s remaining for actual RS-485 work.

**Fix applied:** Restructured `execute_command` with separate timeouts:
1. Lock acquisition: bounded by `LOCK_TIMEOUT_SECONDS` (default 10s)
2. Command execution: bounded by `COMMAND_TIMEOUT_SECONDS` (default 30s), clock
   starts *after* lock is acquired
3. `_refresh_once()` wrapped in `asyncio.wait_for(timeout=COMMAND_TIMEOUT_SECONDS)`

Added `LOCK_TIMEOUT_SECONDS` to config. Tests in `tests/test_hvac_service.py`.

---

## High

### 4. CLI boolean defaults clear hold/temp/out (Bug #1 redux) — RESOLVED

**File:** `cli.py:188-193`
**Reviewers:** All three

```python
temp: bool = typer.Option(False, "--temp", ...)  # Should be None
hold: bool = typer.Option(False, "--hold", ...)  # Should be None
out: bool = typer.Option(False, "--out", ...)     # Should be None
```

Running `pycz2 cli set-zone 1 --heat 68` passed `hold=False` which explicitly
cleared permanent hold — same class of bug as API Bug #1.

**Fix applied:** Changed defaults to `None` with `bool | None` types. Only
explicitly-set flags are passed to the client. Updated existing CLI tests.

---

### 5. `_buffer` not cleared between operations — RESOLVED

**File:** `client.py:47,50-53,119-137`
**Reviewers:** All three

The singleton client's `_buffer` persisted across `connect()`/`close()` cycles.
Stale bytes from a previous session could cause false-positive write confirmations.

**Fix applied:** Added `self._buffer = b""` in `connect()` after establishing the
connection. Test confirms buffer is empty after reconnection.

---

### 6. MQTT publisher bypasses HVACService — RESOLVED

**File:** `api.py:88-131`
**Reviewers:** All three

The MQTT publisher task created its own `lock + client.connection()` path, directly
polling hardware on the 9600-baud bus.

**Fix applied:** Replaced the hardware-polling MQTT publisher with a cache-subscription
publisher (same pattern SSE uses). MQTT now publishes whenever the cache updates —
zero additional bus traffic.

---

### 7. Write reply matching too weak — RESOLVED

**File:** `client.py:308-335`
**Reviewers:** Codex (critical), Claude (noted in investigation doc)

For writes, any `Function.reply` from an allowed destination was accepted without
matching table/row.

**Fix applied:** Write replies now validate that the echoed table/row bytes match the
request. Unrelated replies are skipped (same pattern as read replies).

---

### 8. `set_zone_setpoints()` always writes both rows — RESOLVED

**File:** `client.py:557-582`
**Reviewers:** Codex, Claude

Even for hold-only changes, both row 12 (flags) and row 16 (setpoints) were read
and written — 4 RS-485 operations instead of 2.

**Fix applied:** Dirty row tracking — only reads/writes rows that actually changed.
When both must change, writes setpoints (row 16) before flags (row 12) so temperature
is set before hold is asserted. Tests confirm hold-only writes skip row 16.

---

## Medium

### 9. Dead worker code (~400 lines) — RESOLVED

**File:** `worker.py`
**Reviewers:** All three

`WORKER_ENABLED=False` by default. Entire worker system never used.

**Fix applied:** Deleted `worker.py`. Removed `WORKER_ENABLED`,
`WORKER_POLL_INTERVAL`, `WORKER_RECONNECT_DELAY`, `WORKER_MAX_RECONNECT_DELAY`
from config. Removed all worker imports and branches from `api.py`. Removed
worker-related patches from test fixtures.

---

### 10. API endpoints copy-paste 3-way branching — RESOLVED

**File:** `api.py` (5 POST endpoints, ~80 lines each)
**Reviewers:** All three

Every POST endpoint had identical `if not WORKER_ENABLED / elif WORKER_ENABLED /
else` patterns with unreachable `else` branches.

**Fix applied:** After removing worker code (#9), extracted a shared
`_execute_and_respond()` helper. Each POST endpoint is now a thin wrapper.

---

### 11. MQTT client lifecycle issues — RESOLVED

**File:** `mqtt.py:107-109`
**Reviewers:** Codex, Gemini

`get_mqtt_client()` used `@lru_cache` — a cached dead connection was returned forever.

**Fix applied:** Replaced `@lru_cache` with a manual module-level singleton pattern.
The `MqttClient` class already handles reconnection via `_ensure_connected()`.

---

### 12. `get_status_and_publish()` is dead code — RESOLVED

**File:** `api.py:193-215`
**Reviewer:** Claude

**Fix applied:** Deleted the function.

---

### 13. `func_eq` defined but never used — RESOLVED

**File:** `client.py:285-293`
**Reviewer:** Claude

**Fix applied:** Deleted the function.

---

### 14. Model validator duplicated identically — RESOLVED

**File:** `models.py:98-107,119-128`
**Reviewer:** Claude

`validate_setpoint_relationship` was copy-pasted identically in both
`ZoneTemperatureArgs` and `BatchZoneTemperatureArgs`.

**Fix applied:** Extracted shared `_validate_setpoint_gap()` helper called by both
model validators.

---

## Low

### 15. TCP timeout error message wrong — RESOLVED

**File:** `client.py:112`

Error said "timed out after 10 seconds" but actual timeout was 3 seconds.

**Fix applied:** Changed message to match actual timeout.

---

### 16. Healthcheck creates new httpx client per ping — RESOLVED

**File:** `healthcheck.py:37`
**Reviewers:** All three

Each `send_healthcheck_ping()` created a new `httpx.AsyncClient`.

**Fix applied:** Module-level `httpx.AsyncClient` singleton via `_get_http_client()`.
Also fixed `HEALTHCHECK_BASE_URL` default typo: `tpeet` → `dpeet`.

---

### 17. `build_message` creates Struct on every call — RESOLVED

**File:** `frame.py:83-91`
**Reviewer:** Claude

**Fix applied:** Moved header Struct to module-level `HEADER_STRUCT` constant.

---

### 18. `_refresh_loop` backoff adds to interval — RESOLVED

**File:** `hvac_service.py:342-353`
**Reviewer:** Claude

Total wait on errors was `interval + backoff` when backoff should replace interval.

**Fix applied:** Single `await asyncio.sleep(max(interval, backoff))`. Test confirms
backoff replaces interval rather than adding to it.

---

### 19. CRC endianness mismatch between build and parse — RESOLVED

**File:** `frame.py:55,97`
**Reviewer:** Codex

Frames built with little-endian CRC but parsed with `Int16ub` (big-endian).

**Fix applied:** Changed parser to `Int16ul` (little-endian). Test confirms parsed
checksum field matches the built CRC value.

---

### 20. Connection validation redundant — RESOLVED

**File:** `client.py:69-81`
**Reviewer:** Claude

TCP branch re-validated that `":"` was in `connect_str` but that was already
guaranteed by `__init__`.

**Fix applied:** Removed the redundant check.

---

### 21. `asyncio.Lock` via `lru_cache` cross-loop risk — RESOLVED

**File:** `client.py:597-600`
**Reviewer:** Gemini

`get_lock()` used `@lru_cache` which could bind the lock to the wrong event loop.

**Fix applied:** Replaced with manual module-level singleton (same pattern as
`get_client()` and `get_mqtt_client()`).

---

## Additional Work

### Dependency Updates (March 7, 2026)

All runtime and dev dependencies updated to latest versions:

| Package | Previous | Updated |
|---------|----------|---------|
| fastapi | >=0.115.0 | >=0.135.1 |
| uvicorn[standard] | >=0.34.0 | >=0.41.0 |
| typer | >=0.15.3 | >=0.24.1 |
| rich | >=13.9.4 | >=14.3.3 |
| pydantic | >=2.10.6 | >=2.12.5 |
| pydantic-settings | >=2.7.1 | >=2.13.1 |
| httpx | >=0.28.1 | >=0.28.1 (unchanged) |
| aiomqtt | >=2.4.0 | >=2.5.1 |
| aiosqlite | >=0.21.0 | >=0.22.1 |
| sse-starlette | >=2.2.1 | >=3.3.2 |
| crc | >=7.1.0 | >=7.1.0 (unchanged) |
| construct | >=2.10.70 | >=2.10.70 (unchanged) |
| pyserial-asyncio | >=0.6 | >=0.6 (unchanged) |
| paho-mqtt | >=2.1.0 | >=2.1.0 (unchanged) |

**Removed:** `tenacity` (Finding #2 — retry decorator removed).

Dev dependency updates:

| Package | Previous | Updated |
|---------|----------|---------|
| pytest | >=8.3.4 | >=9.0.2 |
| pytest-asyncio | >=0.25.3 | >=1.3.0 |
| pytest-timeout | >=2.3.1 | >=2.4.0 |
| ruff | >=0.9.6 | >=0.15.5 |
| mypy | >=1.15.0 | >=1.19.1 |
| pylint | >=3.3.4 | >=4.0.5 |
| pyright | >=1.1.396 | >=1.1.408 |

**Added:** `ty>=0.0.21` (Astral's Rust-based type checker), `sloppylint>=0.5.1`
(code smell detection).

### Python 3.14 Compatibility

Verified all 94 tests pass on both Python 3.13.7 and 3.14.3. The key blocker was
`pydantic-core` — version 2.41.5+ supports Python 3.14 via PyO3 updates.
`mypy` `python_version` bumped to `"3.14"`. `requires-python` remains `">=3.13"`
for flexibility.

### Linter Toolchain

Current dev tooling after this review:

| Tool | Purpose | Status |
|------|---------|--------|
| ruff | Linting + formatting | Primary linter (rules: E, F, W, I, UP, B, C4) |
| pyright | Type checking (Microsoft) | Primary type checker, strict mode |
| ty | Type checking (Astral) | Experimental — 2 pre-existing false positives |
| sloppylint | Code smell detection | Advisory — some false positives on `construct` DSL |

**Removed:** mypy (redundant with pyright), pylint (redundant with ruff).
