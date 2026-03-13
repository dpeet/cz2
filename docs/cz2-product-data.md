# CZ2 Product Data Sheet — Carrier ZONECC2KIT01-B

**Source:** [thermostat.guide — Carrier ZONECC2KIT01-B](https://thermostat.guide/carrier/carrier-zonecc2kit01-b-comfort-zone-ii-zoning-system/)
**Fetched:** 2026-03-13
**Why saved locally:** Contains "permanent memory" specification not present in
the owner's manual (comfort_zone_ii.pdf). Relevant to hold-override-bug H2.

---

## System Overview

The Comfort Zone II is a zoning system providing zone control for 2, 4, or 8
areas with individual temperature management.

## Kit Configurations

- ZONECC2KIT01-B: 2-zone kit
- ZONECC4KIT01-B: 4-zone kit
- ZONECC8KIT01-B: 8-zone kit

## Electrical Specifications

- Input: 24 VAC, less than 40 VA
- Dedicated 40 VA, 60 Hz power supply (field-supplied, isolated transformer)
- Wiring: 18-24 gauge thermostat wire

## Environmental Specifications

**Operating conditions:**
- User interface and sensors: 32degF to 104degF at 95% RH (non-condensing)
- Equipment controller and wireless receiver: 32degF to 158degF at 95% RH (non-condensing)

**Storage conditions:**
- User interface and sensors: -40degF to 134degF
- Equipment controller and wireless receiver: -40degF to 185degF

## Programming & Control

- Temperature setpoint range: 40degF to 90degF
- Separate heating and cooling setpoints
- 7-day programming (4 periods: Wake, Day, Evening, Sleep)
- **Permanent memory** for retaining programmed settings
- Copy functions for periods, days, and zones
- Auto changeover (disableable)
- Smart Recovery (heating and cooling)
- Humidity display and control
- Filter change reminder (adjustable)
- Hold function
- Modulating damper control
- Diagnostic error display

## Communication

- RS-485 between system components at 9600 baud

## Applications

- Up to 2 cooling stages / 3 heating stages
- Dual fuel (heat pump with gas furnace backup)

---

## Notes on "Permanent Memory"

The spec lists "permanent memory" as a feature. Based on the owner's manual FAQ
(p.22: "What if my power goes out, will I lose my program?" → "No"), this
refers to non-volatile storage (likely EEPROM) for the 7-day programmed
schedule and system configuration.

**This does NOT necessarily cover hold state.** Hold is a runtime operating
state stored as bitmask bits in Table 1, Row 12 (bytes 9-10). Whether these
bits survive power loss is undocumented and requires empirical testing. See
`docs/todo/hold-override-bug.md` (H2) for investigation details.
