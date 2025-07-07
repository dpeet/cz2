# MountainStat Project Structure

## Root Directory
```
mountainstat/
├── .serena/           # Serena configuration
├── .claude/           # Claude configuration  
├── .vscode/           # VS Code settings
├── public/            # Static assets
├── src/               # Source code
├── .gitignore         # Git ignore rules
├── .mcp.json          # MCP configuration
├── CLAUDE.md          # Claude guidance (comprehensive project docs)
├── README.md          # Basic project info
├── code-cleanup.md    # Cleanup tasks documentation
├── index.html         # Main HTML entry point
├── package.json       # NPM package configuration
├── vite.config.js     # Vite build configuration
└── yarn.lock          # Yarn dependency lock file
```

## Source Directory Structure
```
src/
├── App.jsx            # Main app component - MQTT connection handler
├── App.scss           # Main stylesheet
├── System.jsx         # Primary UI component - thermostat controls
├── thermostat.jsx     # Thermostat display component
├── index.css          # Global styles
├── main.jsx           # React app entry point
├── json_response.js   # Mock HVAC data for development
├── mqttService.jsx    # UNUSED - legacy MQTT service
└── Status.jsx         # UNUSED - legacy status component
```

## Key Files
- **App.jsx**: Manages MQTT WebSocket connection, message parsing, and passes data to System component
- **System.jsx**: Main UI with all thermostat controls, API calls, and state management
- **CLAUDE.md**: Comprehensive documentation including architecture, security issues, and guidelines

## External Dependencies
- MQTT broker: `wss://mqtt.mtnhouse.casa`
- API backend: `https://nodered.mtnhouse.casa/hvac/*`
- Main MQTT topic: `hvac/cz2`

## Build Output
- Development server: http://localhost:5173
- Production build: `dist/` directory (gitignored)