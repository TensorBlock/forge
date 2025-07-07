# Forge Code Style Guide

This document outlines the coding standards and style guidelines for the Forge project.

## Table of Contents

- [Forge Code Style Guide](#forge-code-style-guide)
  - [Table of Contents](#table-of-contents)
  - [Python Style Guidelines](#python-style-guidelines)
    - [Formatting](#formatting)
    - [Imports](#imports)
    - [Comments and Docstrings](#comments-and-docstrings)
  - [Documentation Guidelines](#documentation-guidelines)
  - [Naming Conventions](#naming-conventions)
  - [Type Annotations](#type-annotations)
  - [Code Organization](#code-organization)
    - [Project Structure](#project-structure)
    - [File Structure](#file-structure)
  - [Testing Style](#testing-style)
  - [Commit Messages](#commit-messages)
  - [Code Quality Tools](#code-quality-tools)

## Python Style Guidelines

We generally follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) with some modifications:

### Formatting

- **Indentation**: Use 4 spaces (not tabs)
- **Line Length**: Maximum line length of 100 characters
- **Line Breaks**: Break before binary operators
- **Blank Lines**:
  - 2 blank lines before top-level function and class definitions
  - 1 blank line before method definitions inside a class
  - Use blank lines to separate logical sections

### Imports

- Imports should be at the top of the file
- Group imports in this order, with a blank line between each group:
  1. Standard library imports
  2. Related third-party imports
  3. Local application/library-specific imports
- Use absolute imports rather than relative imports

```python
# Good
import os
import sys
from typing import Dict, List, Optional

import fastapi
import sqlalchemy
from pydantic import BaseModel

from app.core.config import settings
from app.models.user import User
```

### Comments and Docstrings

- Write docstrings for all public modules, functions, classes, and methods
- Use Google-style docstrings:

```python
def function_with_types_in_docstring(param1, param2):
    """Example function with types documented in the docstring.

    Args:
        param1 (int): The first parameter.
        param2 (str): The second parameter.

    Returns:
        bool: The return value. True for success, False otherwise.

    Raises:
        ValueError: If param1 is equal to param2.
    """
    if param1 == param2:
        raise ValueError("param1 may not equal param2")
    return True
```

## Documentation Guidelines

- Use clear, concise language
- Document all functions, classes, and modules with appropriate docstrings
- Keep API documentation up-to-date
- Include examples where appropriate

## Naming Conventions

- **Functions and Variables**: Use `snake_case`
- **Classes**: Use `PascalCase`
- **Constants**: Use `UPPER_CASE_WITH_UNDERSCORES`
- **Private Methods/Variables**: Prefix with a single underscore `_`
- **"Magic" Methods**: Double underscores `__method__`
- **Modules**: Use short, all-lowercase names. Underscores can be used if it improves readability.

Examples:
```python
# Variables
user_id = 42
temporary_value = "temp"

# Functions
def calculate_total_cost():
    pass

# Classes
class UserAccount:
    pass

# Constants
MAX_CONNECTIONS = 100

# Private methods
def _internal_helper():
    pass
```

## Type Annotations

We use type hints throughout the codebase:

```python
def greet(name: str) -> str:
    return f"Hello, {name}"

def get_user_by_id(user_id: int) -> Optional[User]:
    # Function implementation
    pass

def process_items(items: List[Dict[str, Any]]) -> Dict[str, List[int]]:
    # Function implementation
    pass
```

## Code Organization

### Project Structure

```
forge/
├── app/                      # Main application code
│   ├── api/                  # API endpoints
│   │   ├── deps.py           # Dependency injection
│   │   ├── errors/           # Error handling
│   │   └── routes/           # API route definitions
│   ├── core/                 # Core components
│   │   ├── config.py         # Configuration
│   │   ├── security.py       # Security utilities
│   │   └── errors.py         # Core error definitions
│   ├── db/                   # Database related code
│   │   ├── base.py           # Base models
│   │   └── session.py        # DB session
│   ├── models/               # Database models
│   ├── schemas/              # Pydantic schemas
│   ├── services/             # Business logic
│   └── main.py               # Application entry point
├── tests/                    # Test suite
├── docs/                     # Documentation
└── scripts/                  # Utility scripts
```

### File Structure

For Python files, follow this general structure:

1. Module docstring
2. Imports
3. Constants
4. Classes
5. Functions
6. Main block (if applicable)

## Testing Style

- Test files should match the structure of the code they're testing
- Test file names should start with `test_`
- Test function names should be descriptive and follow the pattern `test_<what_is_being_tested>_<expected_outcome>`
- Use pytest fixtures for setup and teardown
- Use clear assertions that will give good feedback when they fail

Example:

```python
def test_user_creation_succeeds_with_valid_data():
    """Test that a user can be created with valid input data."""
    # Test implementation

def test_user_creation_fails_with_invalid_email():
    """Test that user creation fails when email is invalid."""
    # Test implementation
```

## Commit Messages

Good commit messages are important for project maintainability.

- Use the imperative mood ("Add feature" not "Added feature")
- First line should be a short summary (50 chars or fewer)
- Optionally followed by a blank line and a more detailed explanation
- Reference issues/PRs where appropriate: "Fix #123", "Closes #456"

Example:
```
Add JWT authentication for API endpoints

- Implement JWT token generation and validation
- Add authentication dependency to protected routes
- Update tests to include authentication headers

Closes #789
```

## Code Quality Tools

We use the following tools to ensure code quality:

- **Black**: For code formatting
- **isort**: For import sorting
- **flake8**: For style guide enforcement
- **mypy**: For type checking
- **pre-commit**: To automate checks before committing

To set up pre-commit:

```bash
pip install pre-commit
pre-commit install
```
