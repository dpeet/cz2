# Task Completion Checklist

When completing any coding task in the MountainStat project, ensure you:

## Before Committing Code
1. **Remove Debug Code**
   - Remove all `console.log` statements
   - Remove commented-out code blocks
   - Clean up any temporary testing code

2. **Code Quality Checks**
   - Ensure proper error handling with try-catch blocks
   - Add cleanup functions to useEffect hooks
   - Use functional state updates where needed
   - Validate all user inputs (especially temperature ranges: 45-80°F)

3. **React Best Practices**
   - Check for missing dependencies in useEffect arrays
   - Ensure no direct DOM manipulation
   - Verify proper key props in lists
   - Add loading states for async operations

4. **Security Considerations**
   - Never commit API keys or secrets
   - Add authentication headers to API calls (currently missing)
   - Implement CSRF protection where needed
   - Move hardcoded URLs to environment variables

## Build Verification
```bash
# Since no linting/formatting tools are configured, manually:
# 1. Build the project to check for errors
yarn build

# 2. Test in development mode
yarn dev

# 3. Check browser console for runtime errors
```

## Manual Testing Checklist
- [ ] All MQTT connections establish properly
- [ ] Temperature controls respond correctly
- [ ] API calls handle errors gracefully
- [ ] UI loading states display during async operations
- [ ] No console errors in browser DevTools
- [ ] Responsive design works on mobile devices

## Known Issues to Watch For
- MQTT connection may need retry logic
- setError function is undefined in some places
- Over 30 individual state variables could be consolidated
- No automated tests to run