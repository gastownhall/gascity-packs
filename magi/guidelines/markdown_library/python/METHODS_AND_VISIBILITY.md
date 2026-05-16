# Methods, Decorators, and Visibility

### `@staticmethod` Required When No `self`/`cls`
Any method that does not use `self` or `cls` MUST be declared `@staticmethod`. Never rely on an undecorated function inside a class when it is semantically static.

### `@classmethod` Usage
Use `@classmethod` only when construction or class-level state is required. Do not use `@classmethod` when the method is actually static.

### Guard Clauses Required
Exit early for invalid states. Use guard clauses at the top of functions; do not nest the entire function body inside an `if`-block:
```python
def process_user(user: User | None) -> ProcessedUser:
    if user is None:
        raise ValueError("User cannot be None")
    if not user.is_active:
        raise InactiveUserError(f"User {user.id} inactive")
    return ProcessedUser(...)
```

### Method Return Types
Every `def` and `async def` must have a `-> return_type` annotation:
- `__init__` returns `-> None`
- `__str__` returns `-> str`
- `__repr__` returns `-> str`
- `__bool__` returns `-> bool`
- `__len__` returns `-> int`

### Method Visibility
Methods are public by default. Private prefix (`_method`) only for genuine implementation details. **Private methods must never be called from outside their class.**

---
[Back to Overview](./OVERVIEW.md)
