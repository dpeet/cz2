# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mountainstat is a React-based virtual thermostat application for controlling a Carrier CV2 HVAC system. It connects to a local MQTT broker for real-time data and communicates with a Node-RED backend API.

## Development Commands

```bash
# Install dependencies
yarn

# Start development server (includes --host flag for network access)
yarn dev

# Build for production (Home Assistant/Caddy deployment)
yarn build

# Preview production build
yarn preview
```

**Note**: For development, connect using the Tailscale IP address as localhost SSH doesn't hot reload correctly.

## Architecture Overview

### Technology Stack
- **Frontend**: React 18 with functional components and hooks
- **Build Tool**: Vite 5
- **Language**: JavaScript (.jsx files)
- **Styling**: SCSS/Sass
- **Real-time Communication**: MQTT WebSocket (wss://mqtt.mtnhouse.casa)
- **HTTP API**: Axios for Node-RED backend calls (https://nodered.mtnhouse.casa)
- **State Management**: Local React state with hooks

### Key Components
- **App.jsx**: Main component handling MQTT connection and message parsing
- **System.jsx**: Primary UI component for thermostat controls and API interactions
- **Main MQTT Topic**: `hvac/cz2` - Receives JSON thermostat data

### API Endpoints (Node-RED Backend)
- `GET /hvac/system/mode?mode={mode}` - Set system mode
- `GET /hvac/system/fan?fan={mode}` - Set fan mode  
- `GET /hvac/zone/hold/{zone}?enable={true/false}` - Toggle zone hold
- `GET /hvac/zone/temp/{zone}?temp={value}` - Set zone temperature
- `GET /hvac/allmode?allmode={mode}` - Set all zones mode

## Critical Issues to Address

### Security Vulnerabilities
1. **No Authentication**: All API endpoints are unprotected - implement authentication headers
2. **Missing CSRF Protection**: Add CSRF tokens to API requests
3. **Hardcoded URLs**: Move API and MQTT URLs to environment variables

### React Best Practices
1. **Missing useEffect Cleanup**: Add cleanup function to MQTT connection in App.jsx
2. **No Error Boundaries**: Implement error boundary components
3. **Direct DOM Manipulation**: Replace with React state management (System.jsx:213)
4. **State Management**: Consider consolidating 30+ individual state variables into grouped objects

### Error Handling
1. **No MQTT Retry Logic**: Implement exponential backoff for connection failures
2. **Inconsistent API Error Handling**: Create unified error handling wrapper
3. **Undefined setError Function**: Properly implement error state management

## Code Quality Guidelines

### State Updates
Always use functional updates when new state depends on previous state:
```javascript
// Bad
setSystemFanMode(systemFanMode === "Auto" ? "Always On" : "Auto");

// Good  
setSystemFanMode(prevMode => prevMode === "Auto" ? "Always On" : "Auto");
```

### API Calls
Implement consistent error handling and authentication:
```javascript
const apiCall = async (url, params) => {
  try {
    const response = await axios.get(url, {
      params,
      headers: { 'Authorization': `Bearer ${token}` }
    });
    return response.data;
  } catch (error) {
    // Handle error appropriately
    throw error;
  }
};
```

### Input Validation
Validate temperature inputs (45-80°F range) before sending to API:
```javascript
const isValidTemperature = (temp) => temp >= 45 && temp <= 80;
```

## Development Notes

- Remove unused files: `src/mqttService.jsx`, `src/Status.jsx`
- Remove unused imports and console.log statements
- The `src/json_response.js` file contains mock data for development
- No testing framework is currently configured
- Build output is deployed to Home Assistant with Caddy reverse proxy