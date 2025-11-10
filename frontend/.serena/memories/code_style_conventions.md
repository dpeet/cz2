# Code Style and Conventions

## JavaScript/React Conventions
- **File Extension**: `.jsx` for React components
- **React Version**: React 18 with functional components only (no class components)
- **State Management**: React hooks (useState, useEffect, useRef)
- **Component Structure**: 
  - Export default function components
  - Props passed as single parameter object
  - State declarations at top of component

## Naming Conventions
- **Components**: PascalCase (e.g., `System.jsx`, `Thermostat.jsx`)
- **State Variables**: camelCase with descriptive names
  - Pattern: `[stateName, setStateName] = useState(initialValue)`
  - Examples: `zone1temp`, `setZone1Temp`, `systemFanMode`, `setSystemFanMode`
- **Functions**: camelCase (e.g., `handleZoneTemperatureChange`)
- **API URLs**: Snake_case for endpoints (e.g., `/hvac/system/mode`)

## Code Organization
- Import order:
  1. CSS/SCSS imports
  2. External libraries (axios, mqtt, react)
  3. Internal components
  4. Data/constants
- No TypeScript despite dependency in package.json
- No PropTypes validation
- Minimal comments in code

## SCSS/Styling
- Single main SCSS file: `App.scss`
- Using Sass preprocessor features
- Class-based styling with occasional inline styles

## Best Practices to Follow
- Use functional state updates when dependent on previous state
- Add cleanup functions to useEffect hooks
- Handle API errors consistently
- Validate temperature inputs (45-80°F range)
- Remove console.log statements for production
- Use environment variables for API/MQTT URLs