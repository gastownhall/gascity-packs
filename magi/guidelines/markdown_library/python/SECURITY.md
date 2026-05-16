# Security

### Input Validation
Validate all external input at boundaries via Pydantic:
```python
class UserInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
```

### Secret Management
- Load from environment variables.
- Use `repr=False` for sensitive Pydantic fields.
- Never log secrets, tokens, or auth headers.

### SQL Injection Prevention
Always use parameterized queries:
```python
# Correct
await conn.execute("SELECT * FROM users WHERE id = $1", user_id)
# Wrong
await conn.execute(f"SELECT * FROM users WHERE id = {user_id}")
```

### Cryptographic Randomness
Use the `secrets` module for security-sensitive randomness. Never use `random` for security purposes.

---
[Back to Overview](./OVERVIEW.md)
