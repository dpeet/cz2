# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

cz2 is a Perl-based command-line interface for monitoring and controlling Carrier ComfortZone II HVAC systems via RS-485 serial communication. The project reads and writes data frames to/from the HVAC control panel using a custom binary protocol.

## Architecture

### Core Components

1. **Main Script (`cz2`)**: Command-line interface providing high-level commands (status, set_zone, set_system) and low-level commands (read, write, monitor)

2. **Perl Modules**:
   - `Carrier::ComfortZoneII::Interface` - Handles serial/network connections, frame I/O, and protocol implementation
   - `Carrier::ComfortZoneII::FrameParser` - Binary frame parsing using Data::ParseBinary

3. **Helper Script (`czdiff`)**: Utility for reverse-engineering protocol changes by comparing frame dumps

### Communication Protocol

- 9600 baud, 8N1 serial parameters
- Binary frame format with CRC-16 checksums
- Master controller at address 1, panel at address 9
- Tables contain rows of data (e.g., table 1 row 16 contains zone setpoints)

### Key Data Locations

- **System Mode**: Table 1, Row 12, Byte 4
- **Zone Setpoints**: Table 1, Row 16 (cooling bytes 3-10, heating bytes 11-18)
- **Zone Temperatures**: Table 1, Row 24, Bytes 3-10
- **System Time**: Table 1, Row 18
- **Panel Status**: Table 9, Rows 3-5

## Common Development Commands

```bash
# Run status check
./cz2 status

# Monitor all serial bus traffic
./cz2 monitor

# Read specific data (destination, table, row)
./cz2 read 1 1 16

# Set zone temperature (zone 1, heat to 68°F, temporary mode)
./cz2 set_zone 1 heat=68 temp=on

# Set system mode to auto
./cz2 set_system mode=auto

# Dump all known data
./cz2 read_all

# Compare frame dumps for reverse engineering
./czdiff before1 before2 before3 . after1 after2
```

## Configuration

The script reads configuration from `$HOME/.cz2` or path specified in `CZ2_CONFIG` environment variable:

```
connect = hostname:port  # For TCP connection
# OR
connect = /dev/ttyUSB0   # For serial connection

zones = 4                # Number of zones
# OR  
zones = Living Room, Bedroom, Office, Basement  # Zone names

id = 99                  # Device ID on serial bus (optional)
```

## Critical Known Issues

1. **Missing Module Terminator**: `lib/Carrier/ComfortZoneII/Interface.pm` is missing the required `1;` at end of file
2. **Hardcoded Config Path**: Line 17 in `cz2` has hardcoded path instead of using `$ENV{HOME}`
3. **Temperature Decoding Bug**: Negative temperature logic in Interface.pm:302 uses wrong comparison
4. **No Input Validation**: Connection strings and file paths are not validated

## Potential Python Rewrite

A comprehensive Python rewrite plan exists in `potential_python_rewrite.md` that addresses all known issues and adds:
- FastAPI web interface
- MQTT integration  
- Async I/O with proper error handling
- Pydantic models for data validation
- Modern project structure with `uv` dependency management

## Testing

Currently no automated tests. Manual testing procedure:
1. Use `cz2 monitor` to verify serial communication
2. Use `cz2 status` to check data parsing
3. Test zone control with `set_zone` commands
4. Use `czdiff` to verify protocol changes when adding features