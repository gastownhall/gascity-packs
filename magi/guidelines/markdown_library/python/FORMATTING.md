# Formatting

### Indentation
- 4 spaces per level. No tabs.
- Continuation lines use the same 4-space indent.
- Closing brackets do not hang — they sit on the same indentation level as the opening statement.

### Blank Lines
- 2 blank lines between top-level class/function definitions.
- 1 blank line between methods inside a class.
- 1 blank line after class header (class line or class docstring) before the first method/attribute.
- 0 blank lines before any closing bracket/brace/paren.
- Maximum 1 consecutive blank line in code blocks.

### Line Length
- 200 characters maximum.
- Maximize usage of available width before breaking.
- Do not auto-wrap or break for aesthetic preferences.

### Single-Line When It Fits
If a construct fits within 200 characters, it stays on a single line:
```python
def calculate(price: Decimal, discount: float, minimum: Decimal = Decimal("0")) -> Decimal:
config = {"host": "localhost", "port": 8080, "debug": True}
```

### Compact Single-Line Patterns
Use single-line `try`/`except`, `if`/`return`, `for` when the entire statement fits in 200 characters:
```python
try: username, password, tenant, env, env_url = CredentialManager.get_credentials()
except ValueError as e: return {"error": "Failed to get credentials", "details": str(e)}

if not data: return response_data
```

### Trailing Commas
**Prohibited everywhere.** Not in function parameters, not in call arguments, not in literals, not in imports.

### No Vertical Alignment
Never vertically align code across lines (parameters, arguments, imports, etc.). Use the standard 4-space continuation indent instead.

### Delimiter Spacing
No spaces inside delimiters:
```python
items[0]            # not items[ 0 ]
func(arg)           # not func( arg )
{"key": "value"}    # not { "key": "value" }
```

### Comma and Colon Spacing
- One space after every comma; no space before.
- No space before colon in annotations, dict literals, or slice expressions.
- One space after colon in annotations and dict literals.

### Strings
- Double quotes for all strings.
- F-strings for interpolation in application code.
- **Never use f-strings inside `logger.*` calls.**

---
[Back to Overview](./OVERVIEW.md)
