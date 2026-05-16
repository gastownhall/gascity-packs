# Style Summary

| Element | Required Style |
|:--------|:---------------|
| Line Length | 200 max; use full width |
| Indentation | 4 spaces; no tabs |
| Trailing Commas | Prohibited everywhere |
| Strings | Double quotes; f-strings (except in logger calls) |
| Logger Format | Lazy `%s`/`%d`/`%f` only — never f-strings |
| Imports | Three groups; sorted alphabetically; from-imports split |
| `__init__.py` | Empty or `__all__` only |
| Type Hints | Required on every function |
| `Any` Type | Forbidden in application code |
| Casting | Forbidden |
| `if TYPE_CHECKING:` | Forbidden |
| Pydantic | V2 only; in `typings/{PROJECT_NAME}_models/` |
| Enums | In `typings/{PROJECT_NAME}_enums/` only |
| Constants | In `typings/{PROJECT_NAME}_constants/` only |
| TypedDict | Forbidden for internal data |
| Dataclasses | Always `slots=True`; prefer `frozen=True` |
| `None` Checks | `is None` / `is not None` |
| Static Methods | `@staticmethod` required when no `self`/`cls` |
| Backwards Compat | Forbidden |
| Inline Comments | `#` comments forbidden |
| Exception Handling | Specific catches; `logger.exception()` inside `except` |
| Async | No blocking I/O; timeouts mandatory |
| File I/O | `pathlib.Path` preferred; `encoding="utf-8"` always |
| Subprocess | List args; `check=True`; never `shell=True` |
| Entry Points | `raise SystemExit(main())` |
| Logging | `logging` only; no `print()` |
| Source Layout | `src/`, `tests/`, `src/typings/` |

---
[Back to Overview](./OVERVIEW.md)
