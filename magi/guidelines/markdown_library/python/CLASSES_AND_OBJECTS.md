# Classes and Objects

### Class Skeleton with Logger Init
```python
class OrderProcessor:
    """Processes incoming orders."""
    def __init__(self, repository: OrderRepository) -> None:
        self._logger = logging.getLogger(__name__)
        self._repository = repository
```

### Dataclasses Require `slots=True`
Every `@dataclass` decorator must include `slots=True` for memory efficiency:
```python
@dataclass(slots=True)
class Point:
    x: float
    y: float
```

### Prefer `frozen=True` for Value Objects
Use `frozen=True` for immutable data containers. Only omit when mutation is a genuine requirement:
```python
@dataclass(frozen=True, slots=True)
class Coordinate:
    latitude: float
    longitude: float
```

### Protocol for Abstractions
Use `Protocol` for dependency abstraction interfaces:
```python
class Repository(Protocol):
    async def find_by_id(self, id: str) -> Model: ...
    async def save(self, model: Model) -> None: ...
```

### Property Typing
Properties have return-type annotations. Setters type their value parameter:
```python
@property
def name(self) -> str:
    """The user display name."""
    return self._name


@name.setter
def name(self, value: str) -> None:
    self._name = value
```

### Enum Docstrings
Enum classes must have a docstring:
```python
class OrderStatus(Enum):
    """Possible states for an order lifecycle."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
```

---
[Back to Overview](./OVERVIEW.md)
