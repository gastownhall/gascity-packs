# Pydantic Models

### When Required
- API request/response bodies
- Configuration from files/environment
- Data crossing service boundaries
- Structures with validation requirements
- Signatures exceeding the complexity threshold
- Any time typing is unclear or ambiguous (default to a model)

### V2 Syntax Only
- `model_config = ConfigDict(...)` not class-based `Config`
- `field_validator` not `validator`
- `model_validator` not `root_validator`
- `model_dump()` not `.dict()`
- `model_validate()` not `parse_obj()`

### Standard Configuration
```python
from pydantic import BaseModel, ConfigDict, Field


class OrderItem(BaseModel):
    """Represents a single order line item."""
    model_config = ConfigDict(extra="forbid")
    product_id: str = Field(..., min_length=1, max_length=50, description="Product identifier")
    quantity: int = Field(..., gt=0, description="Quantity ordered")
```
Apply settings deliberately:
- `strict=True` prevents type coercion at boundaries.
- `frozen=True` makes instances immutable.
- `extra="forbid"` rejects unknown fields.

### Computed Fields
```python
@computed_field
@property
def full_name(self) -> str:
    return f"{self.first_name} {self.last_name}"
```

### Settings via BaseSettings
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Application configuration loaded from environment."""
    model_config = SettingsConfigDict(env_prefix="APP_", extra="forbid")
    debug: bool = False
    database_url: str = Field(..., description="PostgreSQL connection string")
```

### Discriminated Unions
Use a discriminator field for polymorphic payloads. Do not rely on heuristic union parsing:
```python
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class PaymentCard(BaseModel):
    kind: Literal["card"] = Field(default="card")
    last4: str = Field(..., description="Card last 4 digits")


class PaymentAch(BaseModel):
    kind: Literal["ach"] = Field(default="ach")
    bank_id: str = Field(..., description="Bank identifier")


type PaymentMethod = PaymentCard | PaymentAch
```

### Prohibitions
**NEVER USE A TYPEDICT, BARE CLASS, OR ANYTHING ELSE INSTEAD OF A PYDANTIC MODEL.**

---
[Back to Overview](./OVERVIEW.md)
