# HVAC Protocol and Implementation Details

## Communication Protocol
- **Connection**: RS-485 serial at 9600 baud, 8N1
- **Frame Format**: Binary with CRC-16 checksums
- **Addresses**: Master controller at 1, panel at 9
- **CRC**: CRC-16/CCITT-FALSE (polynomial 0x1021)

## Key Data Locations
Data is organized in tables and rows:

- **System Mode**: Table 1, Row 12, Byte 4
- **Zone Setpoints**: Table 1, Row 16
  - Cooling: bytes 3-10 (one per zone)
  - Heating: bytes 11-18 (one per zone)
- **Zone Temperatures**: Table 1, Row 24, Bytes 3-10
- **System Time**: Table 1, Row 18
- **Panel Status**: Table 9, Rows 3-5

## Temperature Encoding
- Values are in Fahrenheit
- Stored as unsigned bytes
- Special handling for negative temperatures

## Frame Structure
Binary frames parsed using Construct library:
- Destination byte
- Source byte  
- Length byte
- Function byte (enum)
- Data array
- CRC-16 checksum

## Known Issues from Legacy Code
1. Missing module terminator in Perl
2. Hardcoded config paths
3. Temperature decoding bugs
4. No input validation

## Important Implementation Notes
- Use async I/O for all serial communication
- Validate all frames with CRC before processing
- Handle connection failures gracefully
- Support both serial and TCP connections
- Device ID configurable (default 99)