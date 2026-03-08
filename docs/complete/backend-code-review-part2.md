# Backend Code Review Part 2 — March 7, 2026

Follow-up review of the Part 1 fixes. Found secondary issues introduced by the refactoring.

Cross-validated by Claude (Opus 4.6) subagents (7 parallel: Logic, Security, AI-Smell,
Architecture, AsyncIO/FastAPI, Serial Protocol, MQTT), Codex (GPT-5.4), and Gemini
(3.1 Pro Preview).

**Status: Planned** (March 7, 2026).

## Summary

| Severity | Count | Status |
|----------|-------|--------|
| High | 5 | 0/5 |
| Medium | 3 | 0/3 |
| Cleanup | 5 | 0/5 |

---

## High

### 1. Double MQTT publish per command

**File:** `api.py:44-56`
**Reviewers:** MQTT agent, Codex

`_execute_and_respond()` publishes directly to MQTT (line 55-56) AND
`execute_command()` calls `cache.update()` which fires `_notify_subscribers()`,
waking the cache-subscription MQTT publisher task. Every successful command
produces two identical MQTT publishes.

**Fix:** Delete the direct publish from `_execute_and_respond()`. The
cache-subscription publisher handles it. This also aligns with the architectural
decision to use event-driven (cache subscription) publishing — see investigation
notes below.

---

### 2. MQTT publisher task dies permanently on unexpected exception

**File:** `api.py:85-100`
**Reviewers:** MQTT agent, AI-Smell agent, Codex, Gemini

The `mqtt_publisher_task` loop has no try/except around the publish call.
`publish_status()` has its own internal error handling, but if `cache.get()`
throws or an unexpected exception type escapes, the task dies silently and is
discarded from `background_tasks`. MQTT publishing stops for the rest of the
process lifetime with no log.

**Fix:** Add `try/except Exception` with logging inside the `while True` loop,
around the get+publish calls.

---

### 3. MQTT publisher re-publishes stale data on error updates

**File:** `api.py:94-96`
**Reviewers:** MQTT agent, Codex

`cache.update(None, source="error")` fires `_notify_subscribers()`. The publisher
wakes up, calls `cache.get()` (which never returns None — returns stale or empty
status), and publishes stale data to MQTT. The old polling publisher only published
after successful hardware reads.

**Fix:** Check `meta.source != "error"` before publishing. The publisher already
calls `cache.get()` which returns `(status, meta)` — just inspect meta.

---

### 4. `_refresh_once` timeout includes lock wait time

**File:** `hvac_service.py:202-216`
**Reviewers:** Logic agent, Architecture agent, AsyncIO agent, Codex

`execute_command` correctly separates lock acquisition (Step 1, `LOCK_TIMEOUT_SECONDS`)
from command execution (Step 2, `COMMAND_TIMEOUT_SECONDS`). But `_refresh_once`
wraps the entire `_do_refresh()` — including `async with self._op_lock` — in a
single `asyncio.wait_for(timeout=COMMAND_TIMEOUT_SECONDS)`. If a user command holds
the lock for 20s, the refresh only has 10s for RS-485 work under a 30s timeout.

Same bug class as Critical #3 from Part 1, just on the refresh path.

**Fix:** Mirror the `execute_command` pattern: manual `lock.acquire()` with
`LOCK_TIMEOUT_SECONDS`, then `wait_for(_execute(), COMMAND_TIMEOUT_SECONDS)`,
with `finally: lock.release()`.

---

### 5. `_refresh_once` swallows failures — force-refresh returns 200 with stale data

**File:** `hvac_service.py:219-239`
**Reviewer:** Codex

`_refresh_once()` catches all exceptions, writes error to cache, and returns
`await cache.get()` (stale data). This means `POST /update` (which calls
`get_status(force_refresh=True)`) returns HTTP 200 with `"Status refreshed
successfully"` even when the refresh failed.

**Fix:** In `_refresh_once`, re-raise exceptions when called with `force_refresh`
intent. Background auto-refresh should continue to swallow (it has its own
`_consecutive_errors` tracking). Add a `raise_on_error: bool = False` parameter.

---

## Medium

### 6. Double error cache update on command failure

**File:** `hvac_service.py:121,175,179` + `api.py:230,252,273,335,393,420`
**Reviewers:** AI-Smell agent, Codex

`execute_command()` calls `cache.update(None, source="error", error=...)` on
both `TimeoutError` and generic `Exception` before re-raising. Each API endpoint
handler then catches the re-raised exception and calls `cache.update(None,
source="error", error=str(e))` again. Every failed command writes error to cache
twice, bumps version twice, notifies subscribers twice.

**Fix:** Remove the `cache.update()` calls from the API endpoint exception
handlers. The service layer already handled it.

---

### 7. `/status/live` endpoint has no timeout protection

**File:** `api.py:427-450`
**Reviewer:** Architecture agent

`/status/live` uses `async with lock, client.connection():` directly with no
timeout wrapping. If the lock is held by a long command or the HVAC controller
is unresponsive, this endpoint hangs indefinitely.

**Fix:** Wrap in `asyncio.wait_for()` with `COMMAND_TIMEOUT_SECONDS`. This is a
debug/admin endpoint so the blast radius is small, but it should still be bounded.

---

### 8. Write reply matching behavioral change

**File:** `client.py:301-306`
**Reviewers:** Serial Protocol agent, Codex

The old code validated table/row only for read replies (`function == Function.read`).
The new code validates for ALL reply types when both sides have >= 3 bytes. Write
ACKs with < 3 bytes (typical single-byte `[0]`) still work via the `else` branch.
But if the CZ2 controller ever sends a multi-byte write error reply with different
byte 0 (error code instead of 0), it would be silently discarded as a table/row
mismatch, causing a timeout instead of an informative error.

**Fix:** Restore the `function == Function.read` guard so only read replies are
validated against table/row. This matches the Perl legacy behavior and is the
safer default for an incompletely-documented protocol.

---

## Cleanup

### 9. Orphaned config: `COMMAND_QUEUE_MAX_SIZE`

**File:** `config.py:52`

Only used by deleted `worker.py`. Dead setting.

**Fix:** Remove from config.

---

### 10. Orphaned config: `MQTT_PUBLISH_INTERVAL`

**File:** `config.py:31`

No longer used functionally (publisher is cache-subscription, not timer-based).
Still referenced in `__main__.py` log output.

**Fix:** Remove from config and `__main__.py`.

---

### 11. Orphaned method: `set_connection_status()`

**File:** `cache.py:304-337`

Only caller was deleted `worker.py`. Includes stale docstring referencing worker.

**Fix:** Remove the method.

---

### 12. Stale docs reference worker mode

**Files:** `.env.example`, `docs/API_COMMANDS.md`

`.env.example` documents `WORKER_ENABLED`, `WORKER_POLL_INTERVAL`, etc. which no
longer exist. `API_COMMANDS.md` references 202 responses, command queue, and worker
mode. `.env.example` also has old `tpeet` URL in healthcheck comment.

**Fix:** Remove worker references from both files. Fix healthcheck URL.

---

### 13. Test docstring says "RetryError"

**File:** `test_api.py:590`

Docstring reads `"""Test RetryError during update operation."""` but the test now
raises `TimeoutError`. The assertion was updated but the docstring wasn't.

**Fix:** Update docstring to match.

---

## Implementation Order

### Step 1: MQTT publisher fixes (api.py) — highest impact, lowest risk

1. Delete direct MQTT publish from `_execute_and_respond()` (Finding #1)
2. Add try/except + `meta.source` check in MQTT publisher loop (Findings #2, #3)
3. Run tests

### Step 2: Remove duplicate cache error updates (api.py) — reduces noise

4. Remove `cache.update(None, source="error")` from POST endpoint except blocks (Finding #6)
5. Run tests

### Step 3: `_refresh_once` timeout separation (hvac_service.py) — most structural

6. Restructure `_refresh_once` with manual lock.acquire() + wait_for + finally: release()
   mirroring `execute_command` pattern (Finding #4)
7. Add `raise_on_error` parameter, propagate on force_refresh (Finding #5)
8. Run tests

### Step 4: `/status/live` timeout (api.py)

9. Wrap lock+connection in `asyncio.wait_for` (Finding #7)
10. Run tests

### Step 5: Reply matching fix (client.py)

11. Restore `function == Function.read` guard in reply matching (Finding #8)
12. Run tests

### Step 6: Dead code cleanup

13. Remove `COMMAND_QUEUE_MAX_SIZE` and `MQTT_PUBLISH_INTERVAL` from config (Findings #9, #10)
14. Remove `set_connection_status()` from cache.py (Finding #11)
15. Update .env.example and API_COMMANDS.md (Finding #12)
16. Fix test docstring (Finding #13)
17. Run full test suite

---

## Architecture Decision: Cache-Subscription MQTT Publishing

During the review, we investigated whether the cache pub/sub pattern was adding
unnecessary complexity. Conclusion: **keep it**.

- The pub/sub machinery (49 lines in cache.py) already existed for SSE
- MQTT reuses it with ~15 lines of consumer code
- The 3 MQTT bugs are in the consumer, not the pub/sub system
- Removing it would break SSE and force explicit publish calls in 8+ code paths
- The alternative (explicit publishing everywhere) is what caused Finding #6 in Part 1

The fix is to harden the MQTT consumer (Steps 1-2), not replace the pattern.

---

## Cross-Validation Notes

### Codex (GPT-5.4) — new issues found
- Confirmed all High findings
- Found #5 (`_refresh_once` swallowing failures on force-refresh) — missed by Claude agents
- Noted `ENABLE_CACHE=false` is no longer truly honored (accepted as non-issue since
  it defaults to true and there's no documented cacheless mode)

### Gemini (3.1 Pro Preview) — false positives identified
- "Module-level singletons break ASGI event loop" — **Wrong**. Python 3.10+ asyncio.Lock()
  doesn't bind to event loop at creation. AsyncIO agent verified.
- "Boolean None hardware serialization crashes" — **Wrong**. Code checks `if value is not
  None:` before writing bits. None never reaches hardware layer.
- Correctly identified MQTT publisher resilience as must-fix (#2)
- Challenged severity of double-publish (#1) as "irrelevant for homelab" — fair point but
  still a code correctness issue worth fixing

### Key Files

| File | What |
|------|------|
| `backend/src/pycz2/api.py` | MQTT publisher, _execute_and_respond, POST handlers |
| `backend/src/pycz2/hvac_service.py` | _refresh_once, execute_command |
| `backend/src/pycz2/core/client.py` | Reply matching (send_with_reply) |
| `backend/src/pycz2/cache.py` | set_connection_status (to remove) |
| `backend/src/pycz2/config.py` | Dead settings (to remove) |
