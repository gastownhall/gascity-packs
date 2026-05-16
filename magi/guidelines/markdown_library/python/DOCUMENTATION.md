# Documentation

### No Inline Comments
**No `#` comments in application code, ever.** Code is self-documenting; use docstrings and descriptive names.

### Docstrings Required for Public APIs
Google-style docstrings required for public modules, classes, functions, and methods.

### Module-Level Docstrings
Single-line format:
```python
"""Runs the 'GetResourceAttribute' SafetyChain API."""
```

### Class Docstrings
Single-line format:
```python
class ResourceFilter(BaseModel):
    """Resource name filter."""
```

### Function Docstrings
Multi-line format with description followed by indented Args/Returns/Raises sections:
```python
def normalize_email(email: str) -> str:
    """
    Normalize an email for case-insensitive comparison.
      Args:
          email: The input email address.
      Returns:
          A normalized email.
      Raises:
          ValueError: If the email is missing '@'.
    """
    return email.strip().lower()
```

### `if __name__ == "__main__"` Docstrings
Include a docstring in the main block to explain CLI usage.

### Public API Docstring Requirements
- State what it does.
- State input expectations (especially invariants).
- State failure modes (raised exceptions) when non-obvious.
- State boundary behavior.

---
[Back to Overview](./OVERVIEW.md)
