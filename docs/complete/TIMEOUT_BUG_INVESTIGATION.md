# Timeout Bug Investigation — March 7, 2026

## Context

The ComfortZone II (CZ2) HVAC system is controlled via a Python FastAPI backend that communicates over RS-485 (TCP bridge at 10.0.1.20:8899). When users make sequential API calls, the second call reliably times out after 30 seconds.

This was discovered because a Feb 24 temperature change to 45°F (winterization) only applied a **temporary hold** — the follow-up permanent hold call timed out silently. ~10 days later, the CZ2's internal schedule overrode the temporary hold and heated the house to 70°F.

## Bug #1: Pydantic Model Defaults (FIXED)

**File**: `backend/src/pycz2/core/models.py`

`ZoneTemperatureArgs` and `BatchZoneTemperatureArgs` had `temp`, `hold`, and `out` defaulting to `False` instead of `None`. This meant any temperature change that didn't explicitly include `hold=true` would **actively clear** the permanent hold, even though the caller's intent was "don't change hold."

**Fix applied**: Changed defaults from `False` to `None`. The downstream code (`hvac_service.py` and `client.py`) already correctly skipped `None` values. Container rebuilt and verified working.

## Bug #2: Command Timeout Architecture (OPEN)

### Observed Failures

| | Feb 24 | Mar 7 |
|---|---|---|
| Call 1 (temp) | 200 OK in 6.7s | 200 OK in 10.4s |
| Call 2 (hold) | 500 timeout, lock_wait=17.9s | 500 timeout, lock_wait=0.0s |
| Gap between calls | ~92s | ~42s |

### Root Causes (confirmed by Claude + Codex cross-validation)

#### 1. The 30s timeout includes lock wait time

`asyncio.wait_for()` wraps `_execute_with_lock()`, and the lock is acquired *inside* that coroutine. On Feb 24, the MQTT poll held the lock for ~18s, leaving only 12s for the actual RS-485 work.

**File**: `backend/src/pycz2/hvac_service.py:117-184`

```python
async def _execute_with_lock():
    async with self._op_lock:                    # Lock wait is INSIDE timeout
        async with client.connection():
            await client.set_zone_setpoints(...)
            status = await client.get_status_data()  # 9 RS-485 reads
            return status

status = await asyncio.wait_for(
    _execute_with_lock(),
    timeout=settings.COMMAND_TIMEOUT_SECONDS,  # 30 seconds
)
```

#### 2. RS-485 retry logic has no per-operation timeout

`get_frame()` allows up to 50 consecutive empty reads × 5s each = 250s theoretical max. `send_with_reply()` has nested retries (5 inner × 5 frame reads) plus a Tenacity decorator (5 outer retries for ConnectionAbortedError). None of these respect the 30s API deadline.

**Files**:
- `backend/src/pycz2/core/client.py:212` — `get_frame()`, max_failures=50
- `backend/src/pycz2/core/client.py:281` — `send_with_reply()`, Tenacity + inner retries
- `backend/src/pycz2/core/constants.py` — MAX_REPLY_ATTEMPTS=5, MAX_SEND_RETRIES=5, SEND_RETRY_DELAY=0.5s

#### 3. Post-write status refresh is the largest failure surface

Every command does `set_zone_setpoints()` (4 RS-485 ops) + `get_status_data()` (9 RS-485 ops) = 13 total operations. The 9-read status refresh is the most likely place to stall. On Mar 7, the write probably succeeded but the status refresh consumed the remaining budget.

**File**: `backend/src/pycz2/hvac_service.py:174-178`

#### 4. Additional issues identified

- **Stale `_buffer` not cleared on connect/close** — singleton client's `_buffer` persists across operations. Leftover bytes can cause frame mismatches. (`client.py:47, 119, 153`)
- **`set_zone_setpoints()` always reads/writes both rows** even for hold-only changes — unnecessary bus traffic. (`client.py:557-582`)
- **Write reply matching is weak** — for writes, any `Function.reply` from an allowed destination is accepted without matching row/table. (`client.py:308-335`)
- **Background poll/refresh have no timeout** — if they stall, they hold the global lock indefinitely. (`hvac_service.py:272`, `api.py:99`)

### Successful rapid-fire test (same session, after rebuild)

Three commands in quick succession all succeeded (7-10s each), suggesting the CZ2 doesn't inherently need recovery time between commands. The timeout is about retry logic, not device limitations.

```
22:11:09  Call A: {heat: 45, hold: true}  → 10.4s → 200
22:11:26  Call B: {heat: 46}              →  7.3s → 200
22:11:40  Call C: {heat: 45}              →  9.3s → 200
```

## Proposed Fixes (Priority Order)

### P1: Per-operation timing logs

Add timing for every `read_row`/`write_row` call with an operation ID. This will show exactly where stalls happen. Fastest diagnostic value.

**Where**: `client.py` — `read_row()`, `write_row()`, and ideally `get_frame()` retry attempts.

### P2: Separate lock timeout from command timeout

Split into `LOCK_TIMEOUT_SECONDS` + `COMMAND_TIMEOUT_SECONDS`. Start the command clock *after* acquiring the lock. This fixes the Feb 24 class of failure where poll contention eats the command budget.

**Where**: `hvac_service.py:117-184` — restructure `_execute_with_lock()` to use `asyncio.wait_for()` on lock acquisition separately.

### P3: Make post-write status refresh best-effort

The 9-read `get_status_data()` after a write doubles the failure surface. Options:
- Give it a shorter timeout (e.g., 10s) and return cached status on failure
- Move it to background (fire-and-forget, update cache async)
- Skip it entirely and let the next poll cycle update

**Where**: `hvac_service.py:174-178`

### P4: Deadline propagation through client

Pass a monotonic deadline through the stack so `read_row`/`write_row`/`get_frame` respect remaining budget instead of using static retry constants.

**Where**: `client.py` — `send_with_reply()`, `get_frame()`, and callers.

### P5: Reduce get_frame max_failures

50 × 5s = 250s is absurd for a 30s API budget. Reduce to ~10 or tie to a propagated deadline.

**Where**: `client.py:216`

### P6: Clear _buffer on connect/close

Prevent stale bytes from previous operations from interfering with frame parsing.

**Where**: `client.py` — `connect()` and `close()` methods.

### P7: Add timeout to background poll/refresh

Prevent a stalled poll from holding the global lock indefinitely.

**Where**: `api.py:94-100` (MQTT poll), `hvac_service.py:272` (auto-refresh)

## Current State

- **Bug #1 (model defaults)**: Fixed, deployed, verified. Temperature changes now preserve hold state.
- **Bug #2 (timeouts)**: Investigated, root causes confirmed, fixes planned but not yet implemented.
- **HVAC current state**: All zones at 45°F with permanent hold. Verified via API.

## Key Files

| File | What |
|------|------|
| `backend/src/pycz2/core/models.py` | Pydantic API models (Bug #1 fixed here) |
| `backend/src/pycz2/core/client.py` | RS-485 protocol client, retry logic, frame parsing |
| `backend/src/pycz2/core/constants.py` | Retry constants (MAX_SEND_RETRIES, etc.) |
| `backend/src/pycz2/hvac_service.py` | Command execution, timeout wrapping, lock management |
| `backend/src/pycz2/api.py` | FastAPI endpoints, MQTT periodic poll |
| `backend/src/pycz2/config.py` | Settings (COMMAND_TIMEOUT_SECONDS=30, etc.) |
