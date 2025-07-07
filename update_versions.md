# Dependency Update Process

This document outlines the process used to update all dependencies to their latest versions while ensuring compatibility.

## Process Overview

### 1. Retrieve Latest Versions from PyPI API

The most reliable method to get the absolute latest version of each package is to query the PyPI API directly:

```bash
# Get single package version
curl -s https://pypi.org/pypi/PACKAGE_NAME/json | jq -r .info.version

# Get all package versions in one go
for pkg in fastapi uvicorn typer rich pydantic pydantic-settings construct pyserial-asyncio paho-mqtt crc asyncio-mqtt tenacity pytest ruff mypy pylint pyright; do
  echo -n "$pkg: "
  curl -s https://pypi.org/pypi/$pkg/json 2>/dev/null | jq -r .info.version || echo "failed"
done
```

### 2. Update pyproject.toml

Update the version constraints in `pyproject.toml` to use the latest versions retrieved from PyPI:

```toml
dependencies = [
    "fastapi>=0.116.0",
    "uvicorn[standard]>=0.35.0",
    "typer>=0.16.0",
    # ... etc
]
```

### 3. Validate Compatibility with uv sync

After updating versions, run `uv sync` to validate that all dependencies are compatible:

```bash
uv sync
```

This command will:
- Resolve all dependencies and their transitive dependencies
- Report any version conflicts immediately
- Show clear error messages if packages are incompatible

### 4. Handle Conflicts

If `uv sync` reports conflicts:
1. Read the error message to understand which packages conflict
2. Adjust the version constraint for the conflicting package
3. Re-run `uv sync` to verify the resolution

Example conflict resolution:
```
Error: Because only pylint<=3.3.7 is available and pycz2[dev] depends on pylint>=3.4.0...
Solution: Adjust pylint requirement to >=3.3.7
```

## Python Version Upgrade

When upgrading Python version (e.g., to 3.13):

1. Update `requires-python` in `[project]` section:
   ```toml
   requires-python = ">=3.13"
   ```

2. Update `python_version` in `[tool.mypy]` section:
   ```toml
   [tool.mypy]
   python_version = "3.13"
   ```

3. Run `uv sync` to ensure all dependencies are compatible with the new Python version

## Methods That Didn't Work

For reference, these approaches were less effective:

1. **`uv pip list --outdated`** - Only shows outdated packages that are already installed
2. **`pip index versions`** - No output when run through uv's environment
3. **`pip-search` tool** - Crashes with IndexError, appears to be broken
4. **Web search** - Provides approximate versions but not always the absolute latest

## Summary

The combination of PyPI API queries for exact versions + `uv sync` for compatibility validation provides:
- Exact latest versions from the official source
- Immediate feedback on compatibility issues
- Clear error messages for conflict resolution
- Confidence that all dependencies work together

This process ensures we're using the highest possible versions while maintaining a working dependency tree.