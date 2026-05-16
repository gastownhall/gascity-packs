# Code Patterns

**NOTE**: NEVER FUCKING USE `TYPE_CHECKING` IN PYTHON CODE — NO MATTER WHAT.

### Context Managers
```python
with open(path, "r", encoding="utf-8") as f:
    content = f.read()
async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.get(url)
```

### Comprehensions Over Loops
```python
active_emails = [u.email for u in users if u.is_active]
user_lookup = {u.id: u for u in users}
unique_domains = {email.split("@")[1] for email in emails}
```

### Pattern Matching (3.10+)
```python
match status:
    case 200: return "OK"
    case 404: return "Not Found"
    case _: return "Error"
```

### `enumerate` for Index + Value
```python
for i, item in enumerate(items):
    process_item(i, item)
```

### `dict.items()` for Key-Value Iteration
```python
for key, value in data.items():
    process_entry(key, value)
```

### Inline Conditionals
```python
scheme = "http" if is_local else "https"
```

### Configuration Handling
- Parse environment/config at startup.
- Convert raw strings into typed config objects via Pydantic.
- Pass config objects into services rather than reading globals.

**Anti-patterns:**
- Calling `os.getenv()` deep in business logic.
- Sharing mutable global config dicts across modules.

---
[Back to Overview](./OVERVIEW.md)
