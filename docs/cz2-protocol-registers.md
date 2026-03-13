# CZ2 RS-485 Protocol Register Reference

**Source:** [CZII_to_MQTT Wiki — Interpreting Data](https://github.com/jwarcd/CZII_to_MQTT/wiki/Interpreting-Data)
**Fetched:** 2026-03-13
**Why saved locally:** This is the primary protocol reference for all RS-485
register work. GitHub wikis can disappear without notice.

---

## Overview

The Carrier ComfortZone II protocol uses RS-485 at 9600 baud with a
register-based format. Data messages contain a register reference (high byte =
table, low byte = row) with period-delimited bytes.

- **Address 1:** Zone 1 master controller
- **Address 2-8:** Zone 2-8 controllers
- **Address 9:** Equipment controller (CZII panel)

---

## Table 9 — Equipment Controller (Address 9)

### Row 3: Panel Configuration & Temperature Data

| Byte | Meaning |
|------|---------|
| 3 | Panel option switches (8 bits) |
| 4-5 | Outside temperature (2s complement / 16 = degF) |
| 6 | Leaving air temperature (degF) |
| 7 | HPT temperature — indoor coil discharge |
| 8 | Defrost W1 input (0=Off, 1=On) |
| 9 | Defrost W2 input (0=Off, 1=On) |

**Option switch byte 3 mapping:**

| Bit | Switch | Values |
|-----|--------|--------|
| 0 | System Type | 0=AC, 1=Heat Pump |
| 1 | Blower Speed | 0=Single, 1=Two-Stage |
| 2 | Heat Staging | 0=1/2-Stage, 1=3-Stage (Smart) |
| 3 | Recovery Mode | 0=Smart, 1=Conventional |
| 4 | Address Setting | 0=Addr 1, 1=Addr 2 |
| 5 | Test Mode | 0=Normal, 1=Installer Test |
| 6 | Cool Mode | 0=Lo Temp Cool, 1=Lo Temp Off |
| 7 | Dual Fuel | 0=No, 1=Yes |

### Row 4: Damper Positions (Zones 1-8)

Bytes 3-10: damper opening per zone, 0 (fully closed) to 15 (fully open).

### Row 5: Operating State Command

Byte 3 operation bitmask:

| State | Value (Hex) | Binary |
|-------|------------|--------|
| Fan Off | 0x80 | 1000 0000 |
| Fan On | 0xA0 | 1010 0000 |
| Fan + Heat Pump | 0xA1 | 1010 0001 |
| Fan + Aux Heat | 0xAD | 1010 1101 |
| Fan + A/C | 0xB1 | 1011 0001 |

Byte 3 bit assignments:

| Bit | Control | Purpose |
|-----|---------|---------|
| 0 | Y1 | Compressor Stage 1 |
| 1 | Y2 | Compressor Stage 2 |
| 2 | W1 | Aux Heat Stage 1 |
| 3 | W2 | Aux Heat Stage 2 |
| 4 | Reversing Valve | Heat pump mode |
| 5 | Fan State (G) | Blower control |
| 6 | Humidify | Humidification active |
| 7 | De Humidify | Dehumidification active |

---

## Table 2 — Zone Control (Addresses 2-8)

### Row 1: Zone 1 Broadcast (Environmental Data)

| Byte | Meaning |
|------|---------|
| 4 | Humidity level |
| 5-6 | Outside temperature (2s complement / 16 = degF) |

### Row 2: Zone 1 Configuration to Individual Zones

| Byte | Meaning |
|------|---------|
| 3 | Hold flag |
| 5 | Out mode indicator |
| 7 | Zone heating setpoint (degF) |
| 8 | Zone cooling setpoint (degF) |
| 9 | Save flag (Zone 1 sets to 1 for persistence) |

### Row 3: Zone Response to Status Request

| Byte | Meaning |
|------|---------|
| 7-8 | Zone temperature (2s complement / 16 = degF) |
| 9 | Current zone temperature (degF) |
| 10 | Zone heat setpoint (degF) |
| 12 | Zone cool setpoint (degF) |

---

## Table 1 — Zone 1 Master (Address 1)

Responds to remote queries with data for rows 1-34. Not transmitted during
normal operation.

### Row 2: Zone & Schedule Info

| Byte | Meaning |
|------|---------|
| 4 | Number of zones |
| 10 | Zone displayed on LCD |
| 12 | Active schedule for displayed zone (0=Wake, 1=Day, 2=Eve, 3=Sleep) |

### Row 6: Zone 1 Temperature & Time

| Byte | Meaning |
|------|---------|
| 5-6 | Zone 1 temperature (2s complement / 16 = degF) |
| 7 | Zone 1 humidity |
| 14-15 | Time: high=minutes, low=seconds |

### Row 11: Zone Calibration Offsets

Bytes paired in 2s complement (0.5 = +5, 0.0 = 0, 255.255 = -1, 255.251 = -5):
- Bytes 3-4: Zone 1
- Bytes 5-6: Zone 2
- (pattern continues for zones 3-8)

### Row 12: Operating Mode, Hold/Temp Bitmasks, ALL Mode

**This is the critical row for hold override bug investigation.**

| Byte | Meaning |
|------|---------|
| 4 | Mode: 0=Heat, 1=Cool, 2=Auto, 3=E Heat, 4=Off |
| 6 | Effective mode when Auto (0=Heat, 1=Cool) |
| 9 | **Temporary setpoint bitmask** (1 bit per zone, 1=active) |
| 10 | **HOLD mode bitmask** (1 bit per zone, 1=held) |
| 12 | OUT mode bitmask (displays "--", uses 60degH/85degC) |
| 15 | ALL mode: 0=Normal, 1-8=zone number controls all |

Bitmask structure for bytes 9, 10, 12:

| Bit | Zone |
|-----|------|
| 0 (0x01) | Zone 1 |
| 1 (0x02) | Zone 2 |
| 2 (0x04) | Zone 3 |
| 3 (0x08) | Zone 4 |
| 4 (0x10) | Zone 5 |
| 5 (0x20) | Zone 6 |
| 6 (0x40) | Zone 7 |
| 7 (0x80) | Zone 8 |

**Note:** The wiki does NOT document what happens when both temp (byte 9) and
hold (byte 10) bits are set simultaneously for the same zone. The Perl legacy
CLI treats them as mutually exclusive. See `docs/todo/hold-override-bug.md`.

### Row 16: Current Cooling/Heating Setpoints

| Bytes | Meaning |
|-------|---------|
| 3-10 | Zone 1-8 cooling setpoints (degF) |
| 11-18 | Zone 1-8 heating setpoints (degF) |

**Important:** Changes persist only if zone is in HOLD or temporary setpoint
mode; otherwise reverts to programmed schedule.

### Row 17: Installer Configuration (dangerous to modify)

| Byte | Meaning |
|------|---------|
| 3 | Configuration options bitmask (see below) |
| 4 | Clean filter timer (x400 = hours) |
| 5 | Aux heat lockout (x5 = degrees) |
| 6 | Dual fuel crossover (x5 = degrees) |
| 10 | Deadband setting |
| 11 | Heat shutdown |
| 12-13 | Outdoor air offset (2s complement) |
| 14 | Fan operation (0=Normal, 75=Auto when Zone 1 SLEEP) |

Configuration options byte 3:

| Bit | Option | Values |
|-----|--------|--------|
| 0 | Zoning | 0=Enabled, 1=Disabled |
| 1 | Fan with W | 0=Off, 1=On |
| 2 | Fan Mode | 0=Auto, 1=Always On |
| 3 | Auto RH Adjust | 0=Off, 1=On |
| 4 | Humidify | 0=When Heating, 1=Always |
| 5 | Cool to Dehumidify | 0=Off, 1=On |
| 6 | Ignore Lat/HPT | 0=Off, 1=On |
| 7 | Blower Style | 0=Constant, 1=Variable Speed |

### Row 18: Current Date/Time

| Byte | Meaning |
|------|---------|
| 3 | Day of week (0=Sun through 6=Sat) |
| 4 | Hour |
| 5 | Minute |
| 6 | Second |

### Row 19: Equipment Cycle Timers

All values x15 = seconds.

| Byte | Timer | Purpose |
|------|-------|---------|
| 4 | TimeGuard | System protection |
| 5 | Y1 Cycle | Compressor stage 1 min runtime |
| 6 | Y2 Cycle | Compressor stage 2 min runtime |
| 7 | W1 Cycle | Aux heat stage 1 min runtime |
| 8 | W2 Cycle | Aux heat stage 2 min runtime |
| 9 | Staging | Stage changeover delay |
| 10 | Minimum On | Blower minimum runtime |

### Row 24: Current Zone Temperatures

| Byte | Meaning |
|------|---------|
| 3-10 | Zone 1-8 temperatures (degF) |

### Row 31: Auto Changeover Timing

Byte 7: divide by 4 = minutes.

---

## Table 10 — Schedules (Zone 1 Master)

56 rows total: 8 zones x 7 days.

Row numbering:
- Rows 1-7: Zone 1, Sunday-Saturday
- Rows 8-14: Zone 2, Sunday-Saturday
- Rows 15-21: Zone 3, Sunday-Saturday
- (pattern continues for zones 4-8)

Format per row:

| Byte | Meaning |
|------|---------|
| 3 | Wake start hour |
| 4 | Day start hour |
| 5 | Eve start hour |
| 6 | Sleep start hour |
| 7 | Wake minute (0, 15, 30, or 45 only) |
| 8 | Day minute |
| 9 | Eve minute |
| 10 | Sleep minute |
| 11 | Wake heat setpoint (or 196=OUT) |
| 12 | Day heat setpoint (or 188=OUT) |
| 13 | Eve heat setpoint (or 196=OUT) |
| 14 | Sleep heat setpoint (or 188=OUT) |
| 15 | Wake cool setpoint |
| 16 | Day cool setpoint |
| 17 | Eve cool setpoint |
| 18 | Sleep cool setpoint |

---

## Key Notes

- **Temperature conversion:** Two-byte values in 2s complement / 16 = degF.
- **Setpoint persistence:** Row 16 changes only stick if HOLD or temp mode is
  active; otherwise reverts to schedule.
- **Protocol lineage:** Closely mirrors Carrier Infinity system format
  (simplified version).
