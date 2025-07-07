# Suggested Commands for pycz2 Development

## Environment Setup
```bash
# Create and activate virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install -e .          # Install project in editable mode
uv pip install -e .[dev]     # Install with dev dependencies
```

## Running the Application
```bash
# Run CLI commands
pycz2 cli status                              # Get system status
pycz2 cli set-zone 1 --heat 68 --temp        # Set zone temperature
pycz2 cli set-system --mode auto              # Set system mode
pycz2 cli monitor                             # Monitor raw bus traffic

# Run API server (includes MQTT publisher)
pycz2 api                                     # Starts FastAPI on configured port
# or
pycz2 api-server                             # Same as above
```

## Testing Commands
```bash
# Run tests
uv run pytest                                 # Run all tests
uv run pytest -v                              # Verbose output
uv run pytest tests/core/test_frame.py        # Run specific test file
```

## Linting and Code Quality
```bash
# Run linters (must pass all before committing)
uv run ruff check .                          # Fast Python linter
uv run mypy src/                             # Type checking
uv run pylint src/ --errors-only             # Code analysis (errors only)
uv run pyright src/                          # Advanced type checking

# Auto-fix some issues
uv run ruff check . --fix                    # Auto-fix style issues
```

## Development Utilities
```bash
# Dependency management
uv add <package>                             # Add new dependency
uv sync                                      # Sync dependencies
uv lock                                      # Update lock file

# Git commands
git status                                   # Check changes
git diff                                     # View changes
git add -A                                   # Stage all changes
git commit -m "message"                      # Commit changes
```

## Darwin/macOS System Commands
```bash
# File operations
ls -la                                       # List files with details
find . -name "*.py"                          # Find Python files
grep -r "pattern" .                          # Search in files

# Process management  
ps aux | grep pycz2                          # Find running processes
lsof -i :8000                               # Check port usage

# Serial port access (macOS)
ls /dev/tty.*                               # List serial devices
```

## Configuration
```bash
# Copy and edit configuration
cp .env.example .env
nano .env                                    # Edit configuration
```