# MountainStat Project Overview

## Purpose
MountainStat is a React-based virtual thermostat application designed to control a Carrier CV2 HVAC system at the Mountain House. It provides a web interface for monitoring and adjusting temperature settings across multiple zones.

## Tech Stack
- **Frontend Framework**: React 18 with functional components and hooks
- **Language**: JavaScript (.jsx files) - NOT TypeScript despite package.json dependency
- **Build Tool**: Vite 5
- **Styling**: SCSS/Sass
- **Package Manager**: Yarn
- **Real-time Communication**: MQTT over WebSocket (mqtt.js library)
- **HTTP Client**: Axios for API calls
- **UI Components**: react-spinners for loading states

## Key Features
- Real-time HVAC data via MQTT subscription to `hvac/cz2` topic
- Multi-zone temperature control (3 zones)
- System mode control (Heat/Cool/Off/Auto)
- Fan mode control (Auto/Always On)
- Hold functionality per zone
- All zones mode synchronization

## Deployment
- Production build deployed to Home Assistant
- Served via Caddy reverse proxy
- Connects to backend services at mtnhouse.casa domain