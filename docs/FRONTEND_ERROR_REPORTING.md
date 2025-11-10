# Frontend Error Reporting

**Project**: Mountain House Thermostat (mountainstat-main)
**Last Updated**: 2025-10-15
**Status**: ✅ Complete

---

## Overview

The Mountain House Thermostat frontend uses **Sonner** for toast notifications, providing modern, user-friendly error reporting and success feedback. The system handles API errors, MQTT connection issues, and input validation with non-blocking toast messages.

**Error Reporting Maturity**: **8.5/10** (Modern, user-friendly implementation)

---

## Implementation

### Toast Notification System

**Library**: `sonner` v2.0.7 with `lucide-react` v0.545.0 icons

**Features**:
- Success, error, warning, and info notifications
- Auto-dismiss after 5 seconds with manual close button
- Custom icons for each notification type
- Multiple toasts can stack simultaneously
- Non-blocking UI (appears in top-right corner)
- Debounced MQTT connection notifications

**Key Files**:
- `src/components/ui/toaster.jsx` - Toast component with custom icons
- `src/components/ui/toaster.css` - Styling and animations
- `src/main.jsx` - Toaster mounted at application root
- `src/System.jsx` - Toast calls for HVAC operations
- `src/App.jsx` - MQTT connection notifications

**Usage Example**:
```javascript
import { toast } from "sonner";

// Success notification
toast.success("System mode updated", {
  description: "Mode changed to Heat"
});

// Error notification
toast.error("Failed to set temperature", {
  description: error.message
});

// Info notification (immediate feedback)
toast.info("Command sent to HVAC", {
  description: "Setting mode to Cool"
});

// Warning notification (MQTT)
toast.warning("Disconnected from HVAC system", {
  description: "Attempting to reconnect..."
});
```

---

## Error Handling by Category

### 1. API Operations (`System.jsx`)

All HVAC control operations use a three-stage notification pattern:

1. **Info toast**: Immediate feedback when command is sent
2. **Success toast**: Confirmation when operation completes
3. **Error toast**: Descriptive message if operation fails

**Covered Operations**:
- System mode changes (heat/cool/auto/off)
- Fan mode changes (auto/on)
- All mode toggle (all zones active/inactive)
- Hold status changes (per-zone or all zones)
- Temperature setpoint changes

**Example** (System.jsx:137-158):
```javascript
// Immediate feedback
toast.info("Command sent to HVAC", {
    description: `Setting mode to ${newMode}`
});

setSystemModeApi(newMode)
    .then((response) => {
        toast.success("System mode updated", {
            description: `Mode changed to ${newMode}`
        });
    })
    .catch(error => {
        toast.error("Failed to set system mode", {
            description: error.message
        });
    });
```

### 2. Input Validation (`System.jsx:309-313`)

Temperature range validation (45-80°F):
```javascript
if (targetTemperatureSelection < 45 || targetTemperatureSelection > 80) {
    toast.error("Temperature out of range", {
        description: "Please enter a temperature between 45°F and 80°F"
    });
    return;
}
```

HTML5 validation provides additional client-side validation:
```jsx
<input type="number" min="45" max="80" required />
```

### 3. MQTT Connection Events (`App.jsx`)

**Connection State Tracking**:
- `hasConnectedOnce` - Differentiates initial connection from reconnection
- `lastDisconnectToast` - Timestamp for debouncing
- `connectionToastShown` - Prevents toast spam during connection flapping

**Event Handlers**:

| Event | Notification | Debouncing |
|-------|-------------|------------|
| Initial connection | Success: "Connected to HVAC system" | None |
| Reconnection | Success: "Reconnected to HVAC system" | None |
| Connection error | Warning: "Connection issue" | 5 seconds |
| Disconnection | Warning: "Disconnected from HVAC system" | 5 seconds |

**Debouncing Strategy** (App.jsx:102-110):
```javascript
const now = Date.now();
if (!connectionToastShown.current || (now - lastDisconnectToast.current > 5000)) {
    toast.warning("Connection issue", {
        description: "Attempting to reconnect..."
    });
    lastDisconnectToast.current = now;
    connectionToastShown.current = true;
}
```

This prevents notification spam during rapid connect/disconnect cycles while ensuring users are informed of connection state changes.

### 4. MQTT Message Parsing (`App.jsx:88-93`)

Parse errors trigger error toasts:
```javascript
catch (e) {
    console.error("Failed to parse MQTT payload", e);
    toast.error("Failed to parse MQTT message", {
        description: "Received invalid data from HVAC system"
    });
}
```

---

## Test Coverage

### Toast Mock (`System.test.jsx:18-25`)
```javascript
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  }
}));
```

### Error Handling Tests (`System.test.jsx:241-262`)
```javascript
it('should handle API errors gracefully for system mode changes', async () => {
  const { toast } = await import('sonner');

  apiService.systemMode.mockRejectedValueOnce(
    new Error('Network Error')
  );

  await waitFor(() => {
    expect(toast.error).toHaveBeenCalledWith(
      "Failed to set system mode",
      expect.objectContaining({
        description: expect.any(String)
      })
    );
  });
});
```

**Coverage Assessment**:
- ✅ Toast notifications are mocked in tests
- ✅ Error scenarios are tested and verified
- ✅ API service error propagation is tested (apiService.test.js:405-450)

---

## Known Gaps & Future Enhancements

### Critical Gap

| Issue | Impact | Status | Priority |
|-------|--------|--------|----------|
| No React Error Boundary | High | Open | **High** |

**Recommendation**: Add a React Error Boundary component to catch and display component crashes gracefully instead of showing a blank screen.

### Enhancement Opportunities (Low Priority)

1. **Retry Functionality**: Add "Retry" button for network failures
2. **Detailed Error Context**: Include timestamps and troubleshooting hints
3. **Error Severity Levels**: Expand use of info/warning levels for non-critical messages
4. **Error Tracking**: Integrate with error monitoring service (Sentry, LogRocket)
5. **User Preferences**: Allow customization of toast duration/position

---

## Quality Metrics

| Category | Score | Notes |
|----------|-------|-------|
| **Error Detection** | 8/10 | Most errors are caught and handled |
| **User Feedback** | 9/10 | Modern toast system with success + error feedback |
| **Developer Experience** | 8/10 | Toast mocks in tests, clear error messages |
| **Robustness** | 6/10 | No retry logic, no error boundaries |
| **Maintainability** | 9/10 | Clean toast API, good test coverage |

**Overall**: **8.5/10** (Modern, user-friendly implementation)

---

## Related Files

- `src/components/ui/toaster.jsx` - Toast component implementation
- `src/System.jsx` - API error handling and toast notifications
- `src/App.jsx` - MQTT connection event handling
- `src/apiService.js` - API client and error propagation
- `src/__tests__/System.test.jsx` - Error handling tests
- `src/__tests__/apiService.test.js` - API error propagation tests
