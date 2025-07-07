# Task Completion Checklist for pycz2

## Before Marking Any Task as Complete

### 1. Run All Linters (MUST PASS)
```bash
uv run ruff check .              # Style and code issues
uv run mypy src/                 # Type checking
uv run pylint src/ --errors-only # Code analysis
uv run pyright src/              # Advanced type checking
```

### 2. Run Tests
```bash
uv run pytest                    # All tests must pass
```

### 3. Code Review Checklist
- [ ] All functions have proper type hints (including return types)
- [ ] Error handling implemented for async operations
- [ ] Edge cases handled (empty collections, None values, boundaries)
- [ ] No hardcoded values that should be configurable
- [ ] Imports organized correctly (stdlib, third-party, local)
- [ ] No unnecessary comments added
- [ ] Code follows existing patterns in the codebase

### 4. For New Features
- [ ] Add corresponding tests if modifying core functionality
- [ ] Update configuration in .env.example if adding settings
- [ ] Consider MQTT integration if feature affects system state
- [ ] Ensure both CLI and API interfaces are updated if applicable

### 5. For Bug Fixes
- [ ] Verify the fix doesn't break existing functionality
- [ ] Add test case to prevent regression
- [ ] Check if similar bugs exist elsewhere

### 6. Final Steps
- [ ] All linters pass with zero errors
- [ ] Tests pass (if applicable)
- [ ] Code has been tested manually if appropriate
- [ ] No debugging print statements left in code

## Common Issues to Check
- Async functions properly awaited
- File paths use pathlib or handle OS differences
- Serial communication errors handled gracefully
- Configuration values validated before use
- No secrets or sensitive data in code