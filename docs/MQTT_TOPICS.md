# MQTT Topics

This project publishes a compact set of MQTT topics so downstream systems such as Home Assistant can consume HVAC telemetry. All topics are namespaced under the configurable prefix defined by `MQTT_TOPIC_PREFIX` (default: `hvac/cz2`). Toggle publishing with the `MQTT_ENABLED` flag and adjust interval via `MQTT_PUBLISH_INTERVAL`.

## Summary

| Topic | QoS | Retained | Payload | Publish cadence |
| ----- | --- | -------- | ------- | --------------- |
| `<prefix>/status` | 1 | Yes | JSON snapshot of the latest ComfortZone II status, using the legacy "flat" format | On every scheduled poll (`MQTT_PUBLISH_INTERVAL`, default 60s) and immediately after any API command that refreshes state |

## `<prefix>/status`

- **Purpose**: Exposes the full ComfortZone II status in a single retained document so Home Assistant (or any MQTT consumer) can hydrate entities without waiting for the next poll.
- **Encoding**: UTF-8 JSON identical to `GET /status?flat=1`.
- **Structure**: flat key/value pairs plus a `zones` array. Enumerations (system and fan mode) emit title-case strings, Booleans stay `true`/`false`, and `damper_position` is normalised to a string to match legacy consumers.
- **Triggers**:
  - Periodic background poll driven by `MQTT_PUBLISH_INTERVAL` seconds.
  - Manual refresh through `POST /update`.
  - Any mutating API call that ends by fetching fresh status (e.g., mode, fan, zone temperature, or hold changes).

### Example payload

```json
{
  "system_time": "Sun 12:52am",
  "system_mode": "Auto",
  "effective_mode": "Heat",
  "fan_mode": "Auto",
  "fan_state": "Off",
  "active_state": "Idle",
  "all_mode": 1,
  "outside_temp": -1,
  "air_handler_temp": 52,
  "zone1_humidity": 51,
  "compressor_stage_1": false,
  "compressor_stage_2": false,
  "aux_heat_stage_1": false,
  "aux_heat_stage_2": false,
  "humidify": false,
  "dehumidify": false,
  "reversing_valve": false,
  "time": 1676180543,
  "zones": [
    {
      "zone_id": 1,
      "temperature": 47,
      "damper_position": "100",
      "cool_setpoint": 85,
      "heat_setpoint": 55,
      "temporary": false,
      "hold": true,
      "out": false
    },
    {
      "zone_id": 2,
      "temperature": 48,
      "damper_position": "100",
      "cool_setpoint": 85,
      "heat_setpoint": 55,
      "temporary": false,
      "hold": true,
      "out": false
    },
    {
      "zone_id": 3,
      "temperature": 48,
      "damper_position": "100",
      "cool_setpoint": 85,
      "heat_setpoint": 55,
      "temporary": false,
      "hold": true,
      "out": false
    }
  ]
}
```

### Field reference

- **system_time** *(string)* – Panel-reported clock in human-readable form.
- **system_mode / effective_mode** *(string)* – ComfortZone II modes (`Heat`, `Cool`, `Auto`, `EHeat`, `Off`).
- **fan_mode** *(string)* – Fan mode (`Auto`, `On`).
- **fan_state / active_state** *(string)* – Current fan and HVAC output state strings direct from the panel.
- **all_mode** *(number)* – `1` when all zones share setpoints; `0` when individual zone control is active.
- **outside_temp / air_handler_temp / zone1_humidity** *(number)* – Environmental sensors (°F, %, respectively).
- **compressor_stage_* / aux_heat_stage_* / humidify / dehumidify / reversing_valve** *(boolean)* – Equipment stage indicators.
- **time** *(number)* – Unix timestamp (seconds) injected when the payload is built.
- **zones[]** *(array)* – Per-zone telemetry:
  - **zone_id** *(number)* – 1-indexed zone identifier.
  - **temperature** *(number)* – Current zone temperature (°F).
  - **damper_position** *(string)* – Damper opening percentage (`"0"`–`"100"`).
  - **cool_setpoint / heat_setpoint** *(number)* – Active setpoints (°F).
  - **temporary / hold / out** *(boolean)* – Zone flags matching panel semantics.

## Home Assistant Integration Notes

- Use the retained `/status` snapshot with `state_class: measurement` sensors to expose the numeric fields.
- The JSON payload aligns 1:1 with the legacy mountainstat frontend, so existing templates can be reused. Most users create a single MQTT sensor per field (`value_template: '{{ value_json.outside_temp }}'`, etc.).
- Zones are in a zero-based array; address zone *n* via `value_json.zones[n-1]`.
- Because the topic is retained, newly connected Home Assistant instances immediately receive the latest state without waiting for the next poll.
