# Mountainstat Code Review

## Executive Summary

This code review identifies critical security vulnerabilities, React anti-patterns, and code quality issues in the Mountainstat thermostat application. The most critical issues involve unprotected API endpoints, missing error handling, and React hook violations that could cause runtime errors.

## 1. AI/LLM-Specific Vulnerability & Pattern Check

### **CRITICAL: Unused and Conflicting MQTT Libraries**

**File**: `src/App.jsx:8` and `src/mqttService.jsx:1`  
**Issue**: The application imports both `mqtt` and `precompiled-mqtt` packages, but the `mqttService.jsx` file is never used. This creates confusion and potential security vulnerabilities.

```javascript
// App.jsx:8-9
import mqtt from 'mqtt';
import mqttp from 'precompiled-mqtt';  // Imported but never used

// mqttService.jsx - This entire file is unused!
```

**Impact**: Critical - Dead code with hardcoded IP addresses  
**Fix**: Remove the unused `mqttService.jsx` file and the unused import.

### **HIGH: Hardcoded Internal IP Address**

**File**: `src/mqttService.jsx:2`  
**Issue**: Hardcoded internal IP address that shouldn't be in production code.

```javascript
const websocketUrl = "ws://100.73.101.33:9001";
```

**Impact**: High - Security vulnerability  
**Fix**: Remove this file entirely as it's unused.

### **MEDIUM: Unused React Hook Import**

**File**: `src/Status.jsx:3`  
**Issue**: Imports `mqtt-react-hooks` which is not listed in package.json dependencies.

```javascript
import { useMqttState } from 'mqtt-react-hooks';
```

**Impact**: High - Will cause runtime error if this component is used  
**Fix**: Either add the dependency or remove this unused component.

## 2. Security & Input Handling

### **CRITICAL: Unprotected API Endpoints**

**File**: `src/System.jsx:89, 107, 133, 159, 175, 201`  
**Issue**: All API calls to `https://nodered.mtnhouse.casa` lack authentication headers, CSRF protection, or any security measures.

```javascript
// System.jsx:89
axios.get(`https://nodered.mtnhouse.casa/hvac/system/mode?mode=${event.target.value}`)
```

**Impact**: Critical - Anyone can control the HVAC system  
**Fix**: Implement authentication:

```javascript
const apiCall = (url, params) => {
  return axios.get(url, {
    params,
    headers: {
      'Authorization': `Bearer ${getAuthToken()}`,
      'X-CSRF-Token': getCsrfToken()
    },
    withCredentials: true
  });
};
```

### **HIGH: Missing Input Validation**

**File**: `src/System.jsx:378`  
**Issue**: Temperature input accepts any numeric value despite min/max attributes.

```javascript
<input type="number" min="45" max="80" value={targetTemperatureSelection} onChange={handleTargetTemperatureChange} required />
```

**Impact**: High - Could send invalid temperatures to HVAC system  
**Fix**: Add validation in the handler:

```javascript
const handleTargetTemperatureChange = (event) => {
  const value = parseInt(event.target.value);
  if (value >= 45 && value <= 80) {
    setTargetTemperatureSelection(value);
  }
};
```

### **MEDIUM: XSS Vulnerability in Error Handling**

**File**: `src/System.jsx:206`  
**Issue**: `setError` is called but never defined, and error messages could contain user input.

```javascript
.catch(error => {
    setError(error);  // setError is not defined!
    console.log(error)
    setIsTempChangeLoading(false)
})
```

**Impact**: Medium - Potential XSS if error messages are displayed  
**Fix**: Define proper error handling with sanitization.

## 3. Error Handling & Edge Cases

### **CRITICAL: Missing Error Boundaries**

**Issue**: No React error boundaries to catch component errors.  
**Impact**: Critical - Any component error crashes the entire app  
**Fix**: Add error boundary component:

```javascript
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Error caught by boundary:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return <h1>Something went wrong. Please refresh the page.</h1>;
    }
    return this.props.children;
  }
}
```

### **HIGH: No MQTT Connection Error Recovery**

**File**: `src/App.jsx:58-61`  
**Issue**: MQTT errors only log and end connection without retry logic.

```javascript
client.on('error', (err) => {
    console.error('Connection error: ', err);
    client.end();
});
```

**Impact**: High - App becomes unusable after connection error  
**Fix**: Implement exponential backoff retry:

```javascript
const connectWithRetry = (retryCount = 0) => {
  const client = mqtt.connect("wss://mqtt.mtnhouse.casa");
  
  client.on('error', (err) => {
    console.error('Connection error: ', err);
    client.end();
    
    if (retryCount < 5) {
      const delay = Math.min(1000 * Math.pow(2, retryCount), 30000);
      setTimeout(() => connectWithRetry(retryCount + 1), delay);
    }
  });
  
  return client;
};
```

### **HIGH: Race Condition in State Updates**

**File**: `src/System.jsx:110-118`  
**Issue**: State updates based on previous state without using functional updates.

```javascript
if (systemFanMode === "Auto") {
    setSystemFanMode("Always On");  // Race condition!
    setSystemFanModeButtonLabel("Set Auto")
}
```

**Impact**: High - State may be stale  
**Fix**: Use functional state updates:

```javascript
setSystemFanMode(prevMode => prevMode === "Auto" ? "Always On" : "Auto");
```

## 4. React-Specific Anti-Patterns

### **CRITICAL: useEffect Missing Dependencies**

**File**: `src/App.jsx:62`  
**Issue**: useEffect creates MQTT connection but missing dependencies could cause memory leaks.

```javascript
useEffect(() => {
    const client = mqtt.connect("wss://mqtt.mtnhouse.casa");
    // ... no cleanup!
}, []); // Missing dependencies: connectionStatus, initialUpdate, hvacTime
```

**Impact**: Critical - Memory leak from unclosed connections  
**Fix**: Add cleanup and dependencies:

```javascript
useEffect(() => {
    const client = mqtt.connect("wss://mqtt.mtnhouse.casa");
    
    // ... connection logic
    
    return () => {
        client.end();
    };
}, []); // Keep empty if you only want one connection
```

### **HIGH: Direct DOM Manipulation**

**File**: `src/System.jsx:213`  
**Issue**: Direct DOM manipulation instead of React state.

```javascript
const addHoverBorder = (event) => {
    event.target.classList.add("hover-border");
    console.log(event)
}
```

**Impact**: High - Goes against React principles  
**Fix**: Use state or CSS :hover pseudo-class.

### **MEDIUM: Excessive State Variables**

**File**: `src/System.jsx:11-40`  
**Issue**: 30+ individual state variables instead of grouped state.

**Impact**: Medium - Hard to maintain and causes excessive re-renders  
**Fix**: Group related state:

```javascript
const [zones, setZones] = useState({
  1: { temp: null, humidity: null, coolSetPoint: null, heatSetPoint: null, hold: null },
  2: { temp: null, coolSetPoint: null, heatSetPoint: null, hold: null },
  3: { temp: null, coolSetPoint: null, heatSetPoint: null, hold: null }
});

const [systemState, setSystemState] = useState({
  mode: 'Unknown',
  fanMode: 'Unknown',
  allMode: null
});
```

## 5. Performance Issues

### **HIGH: Unnecessary Re-renders**

**File**: `src/System.jsx:42`  
**Issue**: Component re-renders on every prop change without memoization.

```javascript
useEffect(() => { setCZ2Status(props.status) }, [props.status]);
```

**Impact**: High - Performance degradation  
**Fix**: Use React.memo and useMemo:

```javascript
const System = React.memo(function System(props) {
  // ... component logic
});

const memoizedStatus = useMemo(() => props.status, [props.status]);
```

### **MEDIUM: Multiple Sequential API Calls**

**File**: `src/System.jsx:159-171`  
**Issue**: Could batch API calls for hold status changes.

**Impact**: Medium - Slower user experience  
**Fix**: Create a batch endpoint or use Promise.all for parallel requests.

## 6. Code Quality & Maintainability

### **HIGH: Magic Numbers and Strings**

**File**: Throughout the codebase  
**Issue**: Hardcoded values without constants.

```javascript
// System.jsx:64
if (CZ2Status['all_mode'] >= 1 && CZ2Status['all_mode'] <= 8)
```

**Impact**: Medium - Hard to maintain  
**Fix**: Define constants:

```javascript
const HVAC_CONSTANTS = {
  ALL_MODE: {
    MIN: 1,
    MAX: 8,
    OFF: 0
  },
  TEMP_LIMITS: {
    MIN: 45,
    MAX: 80
  }
};
```

### **MEDIUM: Inconsistent Error Handling**

**Issue**: Some API calls have error handling, others don't.  
**Impact**: Medium - Unpredictable behavior  
**Fix**: Create a consistent API wrapper with error handling.

### **LOW: Console.log Statements in Production**

**Files**: Multiple locations  
**Issue**: Debug console.log statements left in code.  
**Impact**: Low - Information disclosure  
**Fix**: Remove or use proper logging library.

## 7. Dead Code

### **Files to Remove**
- `src/mqttService.jsx` - Completely unused
- `src/Status.jsx` - Unused component with missing dependency

### **Unused Imports**
- `src/App.jsx:6` - `data` import used only in commented code
- `src/App.jsx:8` - `mqttp` imported but never used
- `src/System.jsx:3` - `all` imported from axios but never used

### **Commented Code**
- `src/App.jsx:18-30` - Large block of commented development code
- `src/App.jsx:33-38` - Commented axios call

## Priority Action Items

1. **CRITICAL**: Add authentication to API endpoints
2. **CRITICAL**: Fix React hooks and add error boundaries  
3. **CRITICAL**: Add MQTT connection cleanup and retry logic
4. **HIGH**: Remove all dead code and unused files
5. **HIGH**: Implement proper input validation
6. **MEDIUM**: Refactor state management to reduce complexity
7. **MEDIUM**: Add proper error handling throughout
8. **LOW**: Remove console.log statements

## Testing Recommendations

1. Add unit tests for all API calls with mocked responses
2. Test MQTT connection failure scenarios
3. Test temperature input edge cases (below 45, above 80)
4. Test concurrent state updates
5. Add integration tests for the full temperature change flow

## Security Recommendations

1. Implement authentication (OAuth2 or JWT)
2. Add CSRF protection
3. Use HTTPS for MQTT WebSocket connection
4. Add rate limiting to prevent API abuse
5. Sanitize all user inputs
6. Add Content Security Policy headers
7. Regular security audits of dependencies

## Conclusion

The Mountainstat application has several critical issues that need immediate attention, particularly around security and error handling. The lack of authentication on the API endpoints poses a significant security risk, allowing anyone to control the HVAC system. The React implementation has multiple anti-patterns that could lead to runtime errors and poor performance. Addressing these issues will significantly improve the application's security, reliability, and maintainability.