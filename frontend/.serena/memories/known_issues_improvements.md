# Known Issues and Suggested Improvements

## Critical Security Issues
1. **No Authentication**: All API endpoints are completely unprotected
   - Implement JWT or Bearer token authentication
   - Add authentication headers to all axios requests

2. **Missing CSRF Protection**: API vulnerable to cross-site request forgery
   - Implement CSRF tokens for state-changing operations

3. **Hardcoded URLs**: Sensitive endpoints exposed in source
   - Move to environment variables (.env file)
   - Use import.meta.env in Vite

## Code Quality Issues
1. **Missing useEffect Cleanup**: MQTT client not properly cleaned up
   - Add return function to disconnect MQTT on unmount

2. **Excessive State Variables**: Over 30 individual useState calls in System.jsx
   - Consolidate into logical groups (zone1State, zone2State, etc.)

3. **No Error Boundaries**: App crashes on component errors
   - Implement React Error Boundary components

4. **Direct DOM Manipulation**: Found in System.jsx:213
   - Replace with proper React state management

5. **Undefined setError**: Error handler function not implemented
   - Create proper error state and display mechanism

## Performance Issues
1. **No Memoization**: Unnecessary re-renders possible
   - Add React.memo, useMemo, useCallback where beneficial

2. **Missing Debouncing**: API calls on every state change
   - Implement debounce for temperature inputs

3. **No Code Splitting**: Everything loads at once
   - Consider lazy loading for components

## Development Experience
1. **No Linting**: Code style inconsistencies
   - Add ESLint configuration

2. **No Formatting**: Manual formatting required
   - Add Prettier configuration

3. **No Tests**: Zero test coverage
   - Add Jest and React Testing Library

4. **No TypeScript**: Despite TS dependency, using plain JS
   - Consider migrating to TypeScript for type safety