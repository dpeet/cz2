# Command API Documentation

**Version:** 1.0.0
**Base URL:** `http://localhost:8000` (development) or configured API endpoint

This document describes the POST command endpoints for controlling the Carrier
ComfortZone II HVAC system. These endpoints replace the legacy GET-based
commands from the Node-RED backend.

---

## Table of Contents

- [Overview](#overview)
- [Authentication & Environment](#authentication--environment)
- [Response Formats](#response-formats)
- [Command Endpoints](#command-endpoints)
  - [POST /system/mode](#post-systemmode)
  - [POST /system/fan](#post-systemfan)
  - [POST /zones/{zone_id}/temperature](#post-zoneszone_idtemperature)
  - [POST /zones/{zone_id}/hold](#post-zoneszone_idhold)
  - [POST /update](#post-update)
- [Error Handling](#error-handling)
- [Examples](#examples)

---

## Overview

All command endpoints accept JSON payloads and return structured responses
containing both the updated system status and metadata about the operation.
Commands are executed immediately and the system status is refreshed before
returning.

**Key Behaviors:**

- Commands execute synchronously when cache/worker mode is disabled
- With cache enabled (CLI-style mode), commands update immediately and refresh
  the cache
- MQTT notifications are published automatically if `MQTT_ENABLED=true`
- All temperature values are in Fahrenheit
- Zone IDs are 1-indexed (1 to `CZ_ZONES` configured zones)

---

## Authentication & Environment

**Current Status:** No authentication required (local network deployment)

**Deployment Modes:**

| Mode | Description | Response Format |
|------|-------------|-----------------|
| **CLI-style** | Cache enabled, worker disabled (default) | Synchronous with `status` + `meta` |
| **Worker** | Cache + worker enabled (being phased out) | Async 202 response with command tracking |
| **Legacy** | Cache disabled | Synchronous with `status` only |

**Environment Variables:**

- `MQTT_ENABLED`: Auto-publish status updates to MQTT broker
- `ENABLE_CACHE`: Enable state caching (recommended)
- `WORKER_ENABLED`: Enable async command queue (deprecated)

---

## Response Formats

### Success Response (CLI-style mode)

```json
{
  "status": {
    "system_time": "Mon 03:45pm",
    "system_mode": "Auto",
    "fan_mode": "Auto",
    "zones": [ /* zone data */ ],
    /* ...additional status fields... */
  },
  "meta": {
    "connected": true,
    "is_stale": false,
    "source": "writeback",
    "last_updated": "2025-10-03T15:45:23.123456",
    "age_seconds": 0.5
  },
  "message": "System mode set to Heat"
}
```

### Worker Mode Response (202 Accepted)

```json
{
  "command_id": "cmd_abc123",
  "status": "queued",
  "provisional_state": { /* predicted status */ },
  "check_status_at": "/commands/cmd_abc123"
}
```

---

## Command Endpoints

### POST /system/mode

Set the main system operating mode (heating, cooling, auto, etc.).

**Path:** `/system/mode`
**Method:** `POST`

#### Request Body

| Field | Type | Required | Allowed Values | Default | Description |
|-------|------|----------|----------------|---------|-------------|
| `mode` | string | Yes | `"Heat"`, `"Cool"`, `"Auto"`, `"EHeat"`, `"Off"` | - | Target system mode |
| `all` | boolean | No | `true`, `false` | `null` | Enable/disable all-call mode |

**All-Call Mode Behavior:**

- `"all": true` → Enable all-call mode (broadcast mode to all zones)
- `"all": false` → Disable all-call mode
- `"all": null` or omitted → Do not change all-call mode setting

#### Response

**Success (200 OK):**

```json
{
  "status": { /* current system status */ },
  "meta": { /* cache metadata */ },
  "message": "System mode set to Heat"
}
```

**Validation Errors (422):**

- Invalid mode string (not in allowed values)
- Malformed JSON payload

**Server Errors (500):**

- HVAC communication failure
- Internal service error

#### Example

```bash
# Set system to heating mode
curl -X POST http://localhost:8000/system/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "Heat"}'

# Enable auto mode with all-call
curl -X POST http://localhost:8000/system/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "Auto", "all": true}'
```

---

### POST /system/fan

Set the system fan operating mode.

**Path:** `/system/fan`
**Method:** `POST`

#### Request Body

| Field | Type | Required | Allowed Values | Default | Description |
|-------|------|----------|----------------|---------|-------------|
| `fan` | string | Yes | `"Auto"`, `"On"` | - | Target fan mode |

**Fan Mode Behavior:**

- `"Auto"` → Fan runs only when heating/cooling active
- `"On"` → Fan runs continuously (also called "always_on" in legacy system)

#### Response

**Success (200 OK):**

```json
{
  "status": { /* current system status */ },
  "meta": { /* cache metadata */ },
  "message": "Fan mode set to On"
}
```

**Validation Errors (422):**

- Invalid fan mode string
- Missing required `fan` field

#### Example

```bash
# Set fan to always-on mode
curl -X POST http://localhost:8000/system/fan \
  -H "Content-Type: application/json" \
  -d '{"fan": "On"}'
```

---

### POST /zones/{zone_id}/temperature

Set heating and/or cooling setpoints for a specific zone.

**Path:** `/zones/{zone_id}/temperature`
**Method:** `POST`
**Path Parameters:** `zone_id` (integer, 1 to `CZ_ZONES`)

#### Request Body

| Field | Type | Required | Range | Default | Description |
|-------|------|----------|-------|---------|-------------|
| `heat` | integer | No | 45-85°F | `null` | Heating setpoint |
| `cool` | integer | No | 64-99°F | `null` | Cooling setpoint |
| `temp` | boolean | No | - | `false` | Enable temporary hold |
| `hold` | boolean | No | - | `false` | Enable permanent hold |
| `out` | boolean | No | - | `false` | Enable out/away mode |

**Important Notes:**

- At least one of `heat` or `cool` should be provided
- To apply changes, set either `temp` or `hold` to `true`
- `temp=true` → Temporary hold (until next schedule change)
- `hold=true` → Permanent hold (until manually cleared)
- Temperature ranges are validated; out-of-range values return 422
- **Setpoint Gap Requirement:** Heat must be at least 2°F below cool (cool ≥ heat + 2)
  - When setting only `heat`, it's validated against the zone's current `cool` setpoint
  - When setting only `cool`, it's validated against the zone's current `heat` setpoint
  - Violations return 422 with descriptive error message

#### Response

**Success (200 OK):**

```json
{
  "status": { /* current system status */ },
  "meta": { /* cache metadata */ },
  "message": "Zone 2 temperature updated"
}
```

**Client Errors:**

- **404 Not Found:** Invalid zone ID (exceeds configured `CZ_ZONES`)
- **422 Unprocessable Entity:**
  - Temperature out of range (heat: 45-85°F, cool: 64-99°F)
  - Setpoint conflict (heat not at least 2°F below cool)
  - Invalid types or missing required fields

#### Example

```bash
# Set zone 1 to 70°F heating with temporary hold
curl -X POST http://localhost:8000/zones/1/temperature \
  -H "Content-Type: application/json" \
  -d '{"heat": 70, "temp": true}'

# Set zone 2 cooling to 74°F with permanent hold
curl -X POST http://localhost:8000/zones/2/temperature \
  -H "Content-Type: application/json" \
  -d '{"cool": 74, "hold": true}'
```

---

### POST /zones/batch/temperature

Set heating and/or cooling setpoints for multiple zones at once in a single transaction.

**Path:** `/zones/batch/temperature`
**Method:** `POST`

#### Request Body

| Field | Type | Required | Range | Default | Description |
|-------|------|----------|-------|---------|-------------|
| `zones` | array[int] | Yes | 1-8 zone IDs | - | Array of zone IDs to update |
| `heat` | integer | No | 45-85°F | `null` | Heating setpoint for all zones |
| `cool` | integer | No | 64-99°F | `null` | Cooling setpoint for all zones |
| `temp` | boolean | No | - | `false` | Enable temporary hold for all zones |
| `hold` | boolean | No | - | `false` | Enable permanent hold for all zones |
| `out` | boolean | No | - | `false` | Enable out/away mode for all zones |

**Important Notes:**

- At least one of `heat` or `cool` should be provided
- To apply changes, set either `temp` or `hold` to `true`
- All zones in the `zones` array will receive the same setpoints
- This is more efficient than calling `/zones/{zone_id}/temperature` multiple times
- Performs the update in a single HVAC transaction (2-4 serial bus operations vs 12-16)
- Zone IDs are validated; invalid IDs return 404
- Duplicate zone IDs are automatically removed
- **Setpoint Gap Requirement:** Heat must be at least 2°F below cool (cool ≥ heat + 2)
  - When setting only `heat`, it's validated against each zone's current `cool` setpoint
  - When setting only `cool`, it's validated against each zone's current `heat` setpoint
  - If any zone has a conflict, the entire request fails with 422

#### Performance Benefits

**Single Zone Requests:**
- 3 zones × 4 transactions each = 12 serial bus operations (~24 seconds)

**Batch Request:**
- 2 read + 2 write operations = 4 serial bus operations (~6-8 seconds)

**Result:** ~75% faster for multi-zone updates

#### Response

**Success (200 OK):**

```json
{
  "status": { /* current system status */ },
  "meta": { /* cache metadata */ },
  "message": "Zones 1, 2, 3 temperature updated"
}
```

**Client Errors:**

- **404 Not Found:** One or more zone IDs invalid (exceeds configured `CZ_ZONES`)
- **422 Unprocessable Entity:**
  - Temperature out of range (heat: 45-85°F, cool: 64-99°F)
  - Setpoint conflict in any zone (heat not at least 2°F below cool)
  - Invalid types or empty zones array

#### Example

```bash
# Set all 3 zones to 70°F heating with temporary hold
curl -X POST http://localhost:8000/zones/batch/temperature \
  -H "Content-Type: application/json" \
  -d '{"zones": [1, 2, 3], "heat": 70, "temp": true}'

# Set zones 1 and 2 cooling to 74°F with permanent hold
curl -X POST http://localhost:8000/zones/batch/temperature \
  -H "Content-Type: application/json" \
  -d '{"zones": [1, 2], "cool": 74, "hold": true}'
```

---

### POST /zones/{zone_id}/hold

Set or release hold/temporary status for a zone.

**Path:** `/zones/{zone_id}/hold`
**Method:** `POST`
**Path Parameters:** `zone_id` (integer, 1 to `CZ_ZONES`)

#### Request Body

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `hold` | boolean | No | `null` | Enable/disable permanent hold |
| `temp` | boolean | No | `null` | Enable/disable temporary hold |

**Hold Behavior:**

- `"hold": true` → Enable permanent hold
- `"hold": false` → Disable permanent hold
- `"temp": true` → Enable temporary hold
- `"temp": false` → Disable temporary hold
- `null` or omitted → No change to that setting

**Special Case: Zone "all"** (clarify)

The legacy frontend may iterate and call this endpoint for each zone when
setting hold for all zones. There is no direct `/zones/all/hold` endpoint.

#### Response

**Success (200 OK):**

```json
{
  "status": { /* current system status */ },
  "meta": { /* cache metadata */ },
  "message": "Zone 3 hold settings updated"
}
```

**Client Errors:**

- **404 Not Found:** Invalid zone ID

#### Example

```bash
# Enable permanent hold for zone 1
curl -X POST http://localhost:8000/zones/1/hold \
  -H "Content-Type: application/json" \
  -d '{"hold": true}'

# Disable temporary hold for zone 2
curl -X POST http://localhost:8000/zones/2/hold \
  -H "Content-Type: application/json" \
  -d '{"temp": false}'
```

---

### POST /update

Force an immediate status refresh from the HVAC system and publish to MQTT.

**Path:** `/update`
**Method:** `POST`
**Request Body:** None (empty or no payload)

**Purpose:**

Manually trigger a status refresh cycle. This is useful for:

- Forcing cache update after external changes
- Testing MQTT publishing
- Debugging connection issues
- Replacing periodic Node-RED polling

#### Response

**Success (200 OK):**

```json
{
  "status": { /* current system status */ },
  "meta": { /* cache metadata */ },
  "message": "Status refreshed successfully"
}
```

**Worker Mode (202 Accepted):**

```json
{
  "command_id": "cmd_xyz789",
  "status": "queued",
  "message": "Status refresh queued",
  "current_state": { /* last known status */ },
  "check_status_at": "/commands/cmd_xyz789"
}
```

#### Behavior Notes

- Status is fetched directly from HVAC controller
- Cache is updated with fresh data
- MQTT message is published if `MQTT_ENABLED=true`
- This operation may take 1-3 seconds due to serial communication

#### Example

```bash
# Trigger status refresh
curl -X POST http://localhost:8000/update

# With verbose output
curl -v -X POST http://localhost:8000/update
```

---

## Error Handling

### Common HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 200 | Success | Command executed and status updated |
| 202 | Accepted | Command queued (worker mode) |
| 404 | Not Found | Invalid zone ID |
| 422 | Validation Error | Invalid field values, missing required fields |
| 429 | Too Many Requests | Command queue full (worker mode) |
| 500 | Server Error | HVAC communication failure, internal error |
| 503 | Service Unavailable | Worker not enabled (for command tracking) |
| 504 | Gateway Timeout | HVAC controller not responding |

### Error Response Format

```json
{
  "detail": "Could not communicate with HVAC controller."
}
```

### Validation Error Format (422)

```json
{
  "detail": [
    {
      "type": "int_parsing",
      "loc": ["body", "heat"],
      "msg": "Input should be a valid integer",
      "input": "invalid"
    }
  ]
}
```

---

## Examples

### Complete Workflow: Set Zone Temperature

```bash
# 1. Check current status
curl http://localhost:8000/status?flat=1

# 2. Set zone 1 to 68°F heating with temporary hold
curl -X POST http://localhost:8000/zones/1/temperature \
  -H "Content-Type: application/json" \
  -d '{
    "heat": 68,
    "temp": true
  }'

# 3. Verify the change
curl http://localhost:8000/status?flat=1 | jq '.zones[0]'
```

### Complete Workflow: Change System Mode

```bash
# 1. Set system to auto mode
curl -X POST http://localhost:8000/system/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "Auto"}'

# 2. Enable all-call mode
curl -X POST http://localhost:8000/system/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "Auto", "all": true}'

# 3. Force status update and MQTT publish
curl -X POST http://localhost:8000/update
```

### Error Handling Example

```bash
# Attempt invalid temperature (too high)
curl -X POST http://localhost:8000/zones/1/temperature \
  -H "Content-Type: application/json" \
  -d '{"heat": 85, "temp": true}'

# Response: 422 Unprocessable Entity
# {
#   "detail": [
#     {
#       "type": "less_than_equal",
#       "loc": ["body", "heat"],
#       "msg": "Input should be less than or equal to 74",
#       "input": 85
#     }
#   ]
# }
```

---

## Migration from Legacy GET Endpoints

For teams migrating from the Node-RED/Perl backend, here's the mapping:

| Legacy Endpoint | New Endpoint | Payload Changes |
|----------------|--------------|-----------------|
| `GET /hvac/system/mode?mode={mode}` | `POST /system/mode` | `{"mode": "Heat"}` |
| `GET /hvac/system/fan?fan={mode}` | `POST /system/fan` | `{"fan": "On"}` (use "On" not "always_on") |
| `GET /hvac/system/allmode?mode={mode}` | `POST /system/mode` | `{"mode": "Auto", "all": true/false}` |
| `GET /hvac/settemp?mode={mode}&temp={temp}&zone={zone}` | `POST /zones/{zone}/temperature` | `{"heat": 68, "temp": true}` |
| `GET /hvac/sethold?zone={zone}&setHold={on\|off}` | `POST /zones/{zone}/hold` | `{"hold": true/false, "temp": true/false}` |
| `GET /hvac/update` | `POST /update` | No payload |

**Key Differences:**

- All commands now use POST with JSON payloads
- Boolean values are `true`/`false`, not `"on"`/`"off"` strings
- Mode values are title-case strings (`"Heat"` not `"heat"`)
- Temperature mode now uses `temp` field instead of parsing from URL
- Zone "all" iteration must be handled client-side

---

## Additional Resources

- **Status API:** See `GET /status` for retrieving current system state
- **Health Check:** `GET /health` for service health monitoring
- **OpenAPI Docs:** `GET /docs` for interactive API documentation
- **Source Code:** `src/pycz2/api.py` for implementation details

---

**Last Updated:** 2025-10-03
**Maintained By:** AI Migration Coordinator
