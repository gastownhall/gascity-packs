# Prohibited Practices (Absolute Blacklist)

### Never Do
- Use `Any` in application code.
- Use `object` when a specific type is possible.
- Cast to avoid linter errors.
- Suppress with `# type: ignore`.
- **Use `if TYPE_CHECKING:`**.
- Use `__init__.py` for re-exports.
- Define `__all__` outside `__init__.py`.
- Import from directories.
- Use star imports (`from x import *`).
- Lazy imports or imports inside functions/blocks.
- Backwards-compatibility wrappers.
- Define types outside `typings/`.
- Duplicate enums, constants, or Pydantic models.
- Use `*args`/`**kwargs` outside explicit API boundaries.
- **Use `TypedDict` for internal data**.
- Use Pydantic V1 syntax.
- Call private methods externally.
- Omit `@staticmethod` when the method is static.
- Use `print()` in libraries.
- Use f-strings inside logger calls.
- Use `logger.error()` inside `except` blocks (use `logger.exception()`).
- Swallow exceptions or use bare `except:`.
- Block in async functions.
- Use `sys.exit()` (use `raise SystemExit()`).
- Use `==`/`!=` with `None` (use `is`/`is not`).
- Omit `slots=True` on dataclasses.
- Use inline `#` comments.
- String-format SQL.
- Use `shell=True` in `subprocess.run()`.
- Omit `encoding="utf-8"` in text file operations.
- Use trailing commas.
- Break lines under 200 chars for style.

---
[Back to Overview](./OVERVIEW.md)
