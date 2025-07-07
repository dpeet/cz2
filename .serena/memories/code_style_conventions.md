# Code Style and Conventions for pycz2

## Python Style Guidelines
- **Python 3.13+** with modern features
- **PEP 8 compliant** with 88-character line length (Black style)
- **Type hints required** for all functions, including return types
- **Async/await** for all I/O operations
- **No unnecessary comments** - code should be self-documenting

## Import Organization
```python
# Standard library imports
import asyncio
from typing import List, Optional

# Third-party imports
import typer
from rich.console import Console
from pydantic import BaseModel

# Local imports
from .config import settings
from .core.client import ComfortZoneIIClient
```

## Naming Conventions
- **Classes**: PascalCase (e.g., `ComfortZoneIIClient`, `SystemStatus`)
- **Functions/methods**: snake_case (e.g., `get_client`, `build_message`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `CRC_CONFIG`, `FRAME_PARSER`)
- **Private methods**: Leading underscore (e.g., `_validate_frame`)

## Type Annotations
```python
# Always include return types
async def get_status() -> SystemStatus:
    ...

# Use Optional for nullable values
def process_data(value: Optional[int] = None) -> str:
    ...

# Use specific types from typing module
def get_zones() -> List[ZoneStatus]:
    ...
```

## Error Handling
- Use try/except blocks for all async operations
- Handle edge cases (empty collections, None values)
- Provide user-friendly error messages
- Don't expose sensitive details in errors

## Pydantic Models
- Use for all data structures
- Include validation where appropriate
- Use Config classes for model configuration
- Document complex fields with Field descriptions

## File Organization
- Keep modules focused and single-purpose
- Core logic in `src/pycz2/core/`
- API endpoints in `api.py`
- CLI commands in `cli.py`
- Configuration in `config.py`

## Testing Conventions
- Test files mirror source structure
- Use pytest fixtures for common setup
- Test both success and error cases
- Mock external dependencies

## Documentation
- Docstrings for public functions/classes
- Explain "why" not "what" in comments
- Keep README.md updated
- Use type hints as documentation