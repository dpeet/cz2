# Hold Override Bug — March 12, 2026

Thermostat setpoint jumped from 45°F (winterization) to 70°F (scheduled) without
user action. Same symptom pattern as Bug #1 (Feb 24 / March 7), but different
trigger.

## Incident Report

Stephen Peet, March 12, 2026 ~11:42 AM:

> I just saw a high indoor temp alarm from Ambient Weather! But I wasn't at home.
> Just got back to see what happened.
>
> This time I don't see a power bump. I don't know why it did that!
>
> But the heating set point is 70 deg F.
>
> Welp . . . it reset to 45 degF ok.

Key details:
- Ambient Weather alarm = actual indoor temp rise (not a stale reading)
- Stephen initially reported no power bump, but one was later confirmed —
  may or may not be the trigger (previous incidents also correlated with power)
- Setpoint was 70°F on hardware, then returned to 45°F ~8 min later
- "This time" implies recurrence

## Bug #1 Recap (for context)

Feb 24: winterization set temp to 45°F with temporary hold. The follow-up
permanent hold call timed out silently. ~10 days later, CZ2's internal schedule
overrode the temporary hold and heated to 70°F.

March 7 fix: Pydantic defaults changed from `False` to `None`, timeout
architecture fixed. Permanent hold verified working via CLI.

See `docs/complete/TIMEOUT_BUG_INVESTIGATION.md` for full details.

## Investigation Findings

### What was ruled OUT

| Hypothesis | Why ruled out |
|---|---|
| Backend restart writes setpoints | Refresh loop is read-only (`_refresh_once` only calls `get_status_data()`) |
| Bug #1 regression (Pydantic defaults) | All boolean fields confirmed `None` default, only 1 commit since fix |
| MQTT retained message replay | Backend has no MQTT consumer — it only publishes |
| Stale cache artifact | Ambient Weather alarm confirms actual temp rise, not just bad reading |

### What was found: Frontend always sends `temp: true`

**File:** `frontend/src/apiService.js:144-172`

```js
export const setZoneHold = async (zoneId, hold, cachedStatus = null) => {
  const client = getApiClient();

  if (zoneId === "all") {
    // ...
    const response = await client.post("/zones/batch/temperature", {
      zones: zoneIds,
      hold,
      temp: true,  // <-- ALWAYS sends temp: true
    });
    return response.data;
  }

  const response = await client.post(`/zones/${zoneId}/hold`, {
    hold,
    temp: true,  // <-- ALWAYS sends temp: true
  });
  return response.data;
};
```

This was already flagged in the Nov 5, 2025 Hold Mode Analysis
(`docs/complete/HOLD_MODE_ANALYSIS.md`, "Critical Finding #1") but never addressed.

### How temp and hold interact on the CZ2

From the Perl legacy CLI docs (`backend/perl-legacy/cz2:96-108`):

> **temp**: "the zone will keep the current setpoint until the next scheduled
> change, and then automatically resume the pre-programmed schedule"
>
> **hold**: "the zone will ignore all scheduled changes and keep the current
> setpoint forever"
>
> "To change setpoints, you must enable either temporary setpoint mode or HOLD
> mode. Otherwise the controller will quickly revert."

The Perl CLI treats these as independent, mutually-exclusive options and never
sends both simultaneously.

### Hardware registers

Both flags are independent bits in Table 1, Row 12 (see
`docs/cz2-protocol-registers.md` for full register reference):
- **Byte 9**: Temporary hold bitmask (1 bit per zone)
- **Byte 10**: Permanent hold bitmask (1 bit per zone)

When the frontend sends `{hold: true, temp: true}`, the backend writes BOTH bits:

```python
# client.py:557-560
if temporary_hold is not None:
    data12[9 - 3] = (data12[9 - 3] & ~bit) | (int(temporary_hold) << z_idx)
if hold is not None:
    data12[10 - 3] = (data12[10 - 3] & ~bit) | (int(hold) << z_idx)
```

### Unknown: CZ2 behavior when both bits are set

The protocol docs don't cover this case and the Perl legacy never sets both.
Two possible behaviors:

1. **`hold` dominates** — setpoint held forever regardless of `temp` bit. (Safe.)
2. **`temp` processed independently** — at the next schedule transition, the CZ2
   clears `temp` and may also clear `hold` or revert to schedule. (Dangerous.)

If behavior (2) is correct, it explains exactly why:
- March 7 CLI fix worked (`hold: true` only, no `temp`)
- The issue recurred if anyone used the frontend (which sends `temp: true`)
- The pattern is identical to Bug #1 (schedule overrides after temp hold expires)

## Hypotheses

### H1: Frontend `temp: true` undermines permanent hold (HIGH likelihood)

If anyone used the frontend to toggle hold between March 7 and today, the
frontend sent `{hold: true, temp: true}`. The CZ2's schedule transition cleared
the temporary hold, and the scheduled 70°F kicked in.

**Supporting evidence:**
- Exact same symptom as Bug #1 (temp hold expires, schedule overrides)
- Frontend ALWAYS sends `temp: true` (confirmed in current code)
- Perl legacy never sends both flags — designed as independent modes
- March 7 CLI test used `hold: true` only, no `temp` — that worked
- Nov 2025 analysis already flagged this as a "Critical Finding"

**Contradicting:**
- We haven't empirically tested both-bits behavior on the CZ2
- We don't know if anyone used the frontend since March 7

**Verify:** Set zone with `{hold: true, temp: false}`, wait for schedule
transition, confirm hold persists. Then set `{hold: true, temp: true}` and
observe whether next schedule transition clears it.

### H2: CZ2 controller power glitch (MEDIUM likelihood)

Brief power loss reset the CZ2 to its scheduled setpoints (70°F), losing hold
state.

**Supporting evidence:**
- A power bump was later confirmed for this incident (Stephen initially missed it)
- Previous incidents also correlated with power bumps
- Mountain house has unstable power
- Hold state may be volatile (RAM, not EEPROM)

**Research findings (March 13, 2026):**

The CZ2 owner's manual FAQ (p.22) explicitly states: *"What if my power goes
out, will I lose my program?" "No."* — but "program" refers to the 7-day
schedule, NOT hold state. The CZ2 product data sheet lists "permanent memory"
as a spec (see `docs/cz2-product-data.md`), which almost certainly refers to
EEPROM for schedules/config. Hold
state (bits in Table 1, Row 12) is likely volatile RAM — this is the standard
architecture for thermostats. Honeywell's documentation confirms this pattern:
"the thermostat stores the set point and schedule [but] doesn't maintain active
hold states through power loss."

The manual also implies the clock lacks battery backup (instructions treat
clock-setting as routine on p.3/p.12), which is consistent with a simple
microcontroller with EEPROM for persistent config but no battery-backed SRAM.

**Confidence:** ~60% that hold state is volatile. Only empirical testing will
confirm.

**Verify:** Controlled power cycle test — see
`peet_homeautomation/docs/todo/claude-vulcan-automation-migration-test.md`
Test 2b. Consider UPS if hold doesn't survive.

### H3: CZ2 has a maximum hold duration (LOW likelihood)

Some thermostats automatically expire permanent holds after N days. The CZ2
might have a built-in hold timeout (e.g., 7 days) that isn't documented.

**Supporting evidence:**
- Bug #1 occurred ~10 days after hold was set
- This incident is ~5 days after March 7 fix

**Contradicting:**
- No mention in any CZ2 docs or Perl legacy code
- Would be unusual for a permanent hold to have a hidden timer

**Research findings (March 13, 2026):**

The owner's manual describes hold as "indefinite" in multiple places (p.16,
p.21). The p.16 section title is literally *"Overriding the program settings in
a particular zone for an indefinite period of time."* No mention of hold
duration limits, auto-cancel, expiry timers, or maximum hold in any CZ2
documentation or web sources. The related Carrier Infinity Touch has explicit
"Hold Until" functionality, but that's a user-visible temporary hold feature,
not a hidden timer on permanent hold. The inconsistent intervals between
incidents (10 days for Bug #1, 5 days for this one) argue against a fixed timer
and are better explained by H1 (frontend temp: true) or H2 (power glitch).

**Confidence:** ~70% that no hidden timer exists. Empirical test (7+ day hold
with audit logging active) will confirm — see
`peet_homeautomation/docs/todo/claude-vulcan-automation-migration-test.md`
Test 2b.

## Fix Options

### Option A: Send `temp: false` from frontend hold toggle (addresses H1)

**Change:** `frontend/src/apiService.js:160,169` — change `temp: true` to
`temp: false`.

```js
// Before
const response = await client.post(`/zones/${zoneId}/hold`, {
  hold,
  temp: true,
});

// After
const response = await client.post(`/zones/${zoneId}/hold`, {
  hold,
  temp: false,
});
```

Same change for the batch path on line 160.

**Why `temp: false` instead of omitting `temp`?** Omitting `temp` sends
`temporary_hold=None` to the backend, which skips writing the temp bit entirely
(the `if temporary_hold is not None` guard in `client.py:557`). If any zone
already has `temporary_hold=true` on hardware from prior frontend use, the bit
stays set — leaving the zone in the dangerous `hold=true, temp=true` combined
state. Sending `temp: false` explicitly clears any stale temporary hold bit.
*(Flagged independently by both Codex/GPT-5.4 and Gemini 3.1 Pro during
cross-validation, March 13 2026.)*

**Pros:** Simple 2-line fix. Explicitly enforces mutual exclusivity. Aligns with
Perl legacy semantics (hold and temp are independent, mutually-exclusive modes).
**Cons:** Doesn't explain the issue if nobody used the frontend.
**Risk:** Low — the backend already handles `temp: false` correctly (clears the
bit).

### Option B: Backend rejects `hold: true` + `temp: true` together

Add validation in the API layer to reject contradictory flag combinations.

**Pros:** Prevents any client from setting both. Self-documenting.
**Cons:** Breaking change for frontend (need Option A too). Overly strict
if CZ2 actually handles both flags correctly.

### Option C: Audit logging + state change detection

Add structured logging that answers: **who changed what, and when did the
hardware change without a command?**

See full design below in [Monitoring Design](#monitoring-design).

### Option D: UPS for CZ2 controller (addresses H2)

Small UPS to prevent power-glitch resets. Only worth it if H2 is confirmed
(hold state doesn't survive power cycles).

---

## Monitoring Design

### Goal

Be able to distinguish these events in the logs:
1. **User action via web UI** — who (Tailscale identity), what, when
2. **User action via CLI** — local execution, what, when
3. **System auto-refresh** — read-only poll, no command
4. **Unexplained hardware change** — hold/setpoint changed between polls
   with no preceding command (schedule override, power glitch, physical panel)

### What we already have

Caddy sends identity headers for Tailscale users:

```
X-Webauth-User: devon@github
X-Webauth-Name: Devon Peet
X-Webauth-Login: devonpeet
X-Real-IP: 100.68.198.76
```

Trusted IPs get `X-Real-IP` only (identity headers stripped by Caddy).

Logging goes to stderr + rotating file at `~/.cache/pycz2/pycz2.log`
(5 MB × 3 backups). All `pycz2.*` loggers at INFO level.

### Implementation: dedicated `pycz2.audit` logger

Use a dedicated logger name so audit lines are greppable and could later be
routed to a separate file/handler without changing the code. Set
`propagate: false` in `config.py` LOGGING_CONFIG to avoid double-logging
(without it, messages propagate to the parent `pycz2` logger and get logged
twice). *(Flagged by Codex/GPT-5.4 during cross-validation.)*

```python
# In api.py or a new audit.py module
audit = logging.getLogger("pycz2.audit")
```

```python
# In config.py LOGGING_CONFIG["loggers"]
"pycz2.audit": {
    "handlers": ["default", "file"],
    "level": "INFO",
    "propagate": False,
},
```

#### Part 1: Command audit (who did what)

Extract identity from `Request` in each POST handler, pass to a logging helper.

```python
def _get_caller(request: Request) -> str:
    """Build a caller identity string from Caddy/Tailscale headers."""
    user = request.headers.get("x-webauth-user")
    name = request.headers.get("x-webauth-name")
    ip = request.headers.get("x-real-ip", request.client.host if request.client else "unknown")
    if user:
        return f"{name or user} ({ip})"
    return f"anonymous ({ip})"
```

Thread the `Request` into `_execute_and_respond` so the audit line can include
the caller:

```python
async def _execute_and_respond(
    operation: str,
    message: str,
    request: Request,         # <-- add
    **kwargs: Any,
) -> dict[str, Any]:
    caller = _get_caller(request)
    service = await get_hvac_service()
    await service.execute_command(operation, **kwargs)
    status_obj, meta = await service.get_status(force_refresh=False)

    audit.info("command=%s caller=%s args=%s", operation, caller, kwargs)

    return {
        "status": _status_payload(status_obj),
        "meta": meta.to_dict(),
        "message": message,
    }
```

Each POST handler already has (or can easily add) `request: Request` as a
parameter — FastAPI injects it automatically.

**CLI audit:** The CLI doesn't go through FastAPI. Add a similar `audit.info`
line in `cli.py` command functions with `caller=cli`.

**Example log output:**

```
INFO 2026-03-12 11:40:03 [pycz2.audit] command=set_zone_setpoints caller=Devon Peet (100.68.198.76) args={'zones': [1, 2, 3], 'hold': True, 'temporary_hold': True}
INFO 2026-03-12 11:40:03 [pycz2.audit] command=set_zone_setpoints caller=anonymous (10.0.1.5) args={'zones': [1], 'heat_setpoint': 68}
INFO 2026-03-12 14:30:00 [pycz2.audit] command=set_zone_setpoints caller=cli args={'zones': [1], 'hold': True}
```

#### Part 2: State change detection (hardware changed without a command)

In `_refresh_once`, compare previous cached status with fresh hardware read.
Log when hold, setpoint, or mode changes between polls with no preceding
command.

```python
# In hvac_service.py _refresh_once, BEFORE cache.update():
if source == "auto_refresh":
    prev_status, prev_meta = await cache.get()
    if prev_status and prev_meta.source != "error" and prev_status.zones and status.zones:
        for i, (prev, curr) in enumerate(zip(prev_status.zones, status.zones)):
            changes = []
            if prev.hold != curr.hold:
                changes.append(f"hold={prev.hold}->{curr.hold}")
            if prev.temporary != curr.temporary:
                changes.append(f"temp={prev.temporary}->{curr.temporary}")
            if prev.heat_setpoint != curr.heat_setpoint:
                changes.append(f"heat={prev.heat_setpoint}->{curr.heat_setpoint}")
            if prev.cool_setpoint != curr.cool_setpoint:
                changes.append(f"cool={prev.cool_setpoint}->{curr.cool_setpoint}")
            if changes:
                audit.warning(
                    "UNEXPECTED zone=%d %s source=%s (no preceding command)",
                    i + 1, " ".join(changes), source,
                )
```

This only fires for `auto_refresh` source — command-triggered refreshes are
already logged by Part 1. This is the "smoking gun" that would have caught
today's incident.

**Important:** Read the old cache state (`prev_status, prev_meta = await
cache.get()`) **before** `cache.update(status, ...)`, not after. Also skip the
comparison when `prev_meta.source == "error"` — the first successful poll after
a disconnect would otherwise false-positive as an "unexpected change" for every
zone. *(Flagged by Codex/GPT-5.4 during cross-validation.)*

Note: legitimate CZ2 schedule transitions (wake/sleep/leave periods) will also
trigger these warnings. This is expected and desired — these are exactly the
events we want visibility into, since they're indistinguishable from the bug
symptom without audit context.

**Example log output:**

```
WARNING 2026-03-12 11:38:00 [pycz2.audit] UNEXPECTED zone=1 hold=true->false temp=true->false heat=45->70 source=auto_refresh (no preceding command)
WARNING 2026-03-12 11:38:00 [pycz2.audit] UNEXPECTED zone=2 hold=true->false temp=true->false heat=45->70 source=auto_refresh (no preceding command)
```

### Future improvements (not in scope now)

- **SQLite audit table:** persist audit events in the existing cache DB, expose
  via `GET /audit` endpoint for frontend "activity log" view
- **MQTT audit topic:** publish to `hvac/cz2/audit` so Home Assistant can
  trigger alerts on unexpected state changes

---

## Recommended Plan

- [x] **Step 1:** Apply Option A (change `temp: true` to `temp: false` in frontend) —
  explicitly clears stale temporary hold, lowest risk, highest likelihood of fix
  *(Done 2026-03-13)*
- [x] **Step 2:** Apply Option C (audit logging + state change detection) — catches
  any future recurrence with full diagnostic context (who, what, when)
  *(Done 2026-03-13 — `pycz2.audit` logger, `_get_caller()`, command audit in all
  POST handlers, `UNEXPECTED` warnings in `_refresh_once`. CLI audit deferred.)*
- [x] **Step 3:** Ask Stephen if anyone used the frontend between March 7-12 —
  inconclusive, Stephen doesn't know. H1 can't be confirmed or ruled out this way.
  Audit logging (Step 2) will catch it going forward.
- [ ] **Step 4:** Empirical CZ2 test — set `{hold: true, temp: false}` on one zone
  and `{hold: true, temp: true}` on another, wait for schedule transition, compare.
  Audit logging from Step 2 will passively catch this going forward.
- [ ] **Step 5:** Test whether hold state survives a CZ2 power cycle (informs H2
  and whether a UPS is worthwhile). Test procedure documented in
  `peet_homeautomation/docs/todo/claude-vulcan-automation-migration-test.md` (Test 2b).

### Follow-ups from Hold Mode Analysis (Nov 2025)

These were flagged in `docs/complete/HOLD_MODE_ANALYSIS.md` but never addressed.
Not blocking the bug fix, but worth doing alongside or after.

- [ ] **F1: Decouple hold and temp in frontend API service.** Currently
  `setZoneHold()` hardcodes `temp: false` (previously `true`). Go further:
  accept `temp` as a parameter so the frontend can set hold-only, temp-only, or
  both explicitly. Gives the UI flexibility without backend changes.
- [ ] **F2: Add `--hold/--no-hold` and `--temp/--no-temp` to CLI.** The CLI
  defaults were fixed to `None` (Bug #1), but there's no way to explicitly clear
  hold via CLI — you can only set it or leave it unchanged. Typer supports
  `--flag/--no-flag` syntax natively.
- [ ] **F3: Document hold vs temp behavior in API docs.** `docs/API_COMMANDS.md`
  doesn't explain the interaction between `hold` and `temp` flags, that they're
  independent bits, or the consequences of setting both. Add a section to the
  `/zones/{id}/hold` and `/zones/{id}/temperature` entries.
- [ ] **F4: Show hold type in UI.** The frontend displays "[HOLD]" for any hold
  type. Distinguish `[HOLD]` (permanent) vs `[TEMP]` (temporary) vs `[HOLD+TEMP]`
  (both set — which is the problematic state). This would have helped debug this
  incident — Stephen would have seen the wrong hold type.

## All Files Involved

| File | Change | Step |
|---|---|---|
| `frontend/src/apiService.js:157-170` | Change `temp: true` to `temp: false` in both code paths | 1 |
| `frontend/src/__tests__/apiService.test.js` | Update 3 test assertions to expect `temp: false` | 1 |
| `backend/src/pycz2/api.py` | Add `_get_caller()`, thread `request`, add audit logging | 2 |
| `backend/src/pycz2/hvac_service.py` | Add state change detection in `_refresh_once` (read old cache before update, skip on error source) | 2 |
| `backend/src/pycz2/cli.py` | Add audit logging to set commands; add `--no-hold`/`--no-temp` | 2, F2 |
| `backend/src/pycz2/config.py` | Add `pycz2.audit` logger config with `propagate: False` | 2 |
| `frontend/src/apiService.js` | Accept `temp` parameter in `setZoneHold()` | F1 |
| `frontend/src/thermostat.jsx` | Show hold type indicator (`[HOLD]`/`[TEMP]`/`[HOLD+TEMP]`) | F4 |
| `backend/docs/API_COMMANDS.md` | Document hold vs temp interaction | F3 |

---

## Cross-Validation Notes (March 13, 2026)

Plan reviewed by Codex/GPT-5.4 and Gemini 3.1 Pro. Both models independently
flagged the same critical issue plus several medium-severity items. All
corrections have been incorporated into the plan above.

### Critical (incorporated)

**`temp: false` instead of omitting `temp`** — Both LLMs flagged that removing
`temp: true` (sending `None`) leaves stale hardware bits unchanged. If any zone
already has `temporary_hold=true` from prior frontend use, it stays set. Sending
`temp: false` explicitly clears it. *(Codex + Gemini)*

### Medium (incorporated)

- **Audit logger `propagate: False`** — Without it, `pycz2.audit` messages
  propagate to parent `pycz2` logger → double logging. *(Codex)*
- **State detection error-source guard** — First successful poll after a
  disconnect false-positives as "unexpected change" unless previous meta source
  is checked. *(Codex)*
- **State detection cache ordering** — Must read old cache before
  `cache.update()`, not after. *(Both — confirmed the plan's existing concern)*

### Low / informational (not actioned)

- Schedule transitions trigger "unexpected change" warnings — desired behavior,
  these are exactly the events we want to see. *(Gemini)*
- "Hold all" audit message says "temperature updated" — cosmetic, defer.
  *(Codex)*
- CLI mutations bypass FastAPI audit — already scoped as separate work in Step 2.
  *(Codex)*

### Gemini false positives

- "Destructive batch clears" concern about `temp: false` wiping active temp
  overrides when clearing hold — this is desired behavior (turning off hold
  should also turn off temp).
