# Modern Python Features

Target Python 3.14+ for new projects; 3.11+ minimum for existing projects.

### Type Parameter Syntax (3.12+)
```python
def first[T](items: list[T]) -> T | None:
    return items[0] if items else None


class Stack[T]:
    def __init__(self) -> None:
        self._items: list[T] = []
```

### `Self` for Fluent Interfaces
```python
from typing import Self


class Builder:
    def with_name(self, name: str) -> Self:
        self._name = name
        return self
```

### `type` Statement Aliases (3.12+)
```python
type UserId = str
type Timestamp = datetime
type Headers = dict[str, str]
```

---
[Back to Overview](./OVERVIEW.md)
