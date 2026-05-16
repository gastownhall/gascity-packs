# Logging

### Never Use `print()`
All output goes through the `logging` system. `print()` is allowed only in CLI entry-point scripts for direct user output.

### Lazy Formatting Only in Logger Calls
Logger calls MUST use lazy `%s`/`%d`/`%f` formatting, NOT f-strings. Lazy formatting avoids string interpolation when the log level is disabled:
```python
# Correct
logger.info("Processing order order_id=%s", order.id)
# Wrong
logger.info(f"Processing order order_id={order.id}")
```

### `logger.exception()` Inside `except`
Use `logger.exception()` (not `logger.error()`) inside `except` blocks. It automatically attaches the current traceback.

### Structured, Grep-Friendly Messages
Use `key=value` format with lazy formatting.

### Log Levels
| Level | Purpose |
|:------|:--------|
| DEBUG | Detailed diagnostic information |
| INFO | Confirmation of expected operations |
| WARNING | Unexpected but handled situations |
| ERROR | Failures requiring attention (use **outside** `except` blocks) |
| CRITICAL | System-level failures |
| EXCEPTION | Failures inside `except` blocks (auto-includes traceback) |

### Never Log Secrets
Never log passwords, API keys, tokens, or PII. Use `repr=False` on sensitive Pydantic fields.

---
[Back to Overview](./OVERVIEW.md)
