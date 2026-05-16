# Boundaries and Validation

### Boundary Definition
A boundary is any interface where inputs are not already trusted and typed:
- HTTP handlers, CLI parsing, environment variables, config files
- File I/O, network I/O, subprocess output
- DB rows, message queues, cache values, third-party SDK payloads

### Boundary Rule
- Validate at the boundary once.
- Convert input into typed Pydantic models or typed primitives.
- Keep internal code operating on typed objects only.
- Re-validate only when merging new untrusted inputs.

### Boundary Implementation Pattern
```python
from pydantic import BaseModel, ConfigDict, Field


class CreateWidgetRequest(BaseModel):
    """Request model for widget creation."""
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    widget_id: str = Field(..., description="Caller-supplied stable identifier")
    name: str = Field(..., description="Human-readable name")
    quantity: int = Field(..., gt=0, description="Units requested")


def create_widget(req: CreateWidgetRequest) -> str:
    return f"{req.widget_id}:{req.name}:{req.quantity}"
```

**Anti-patterns:**
- Validating in the middle of business logic
- Accepting raw `dict` in public APIs
- Passing untyped JSON across modules

---
[Back to Overview](./OVERVIEW.md)
