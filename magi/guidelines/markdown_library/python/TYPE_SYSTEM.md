# Type System

### Mandatory Typing
Every function — including private helpers and closures — has complete type annotations. Every attribute and instance variable is typed. Never accept implicit `Any` from untyped libraries without stubs. Complex signatures require Pydantic models. **When in doubt, use a Pydantic model.**

### `Any` Is Forbidden
`Any` disables type checking entirely and propagates through the codebase. Permitted only in:
- Pydantic model fields for genuinely heterogeneous external data received from external systems (must be isolated at boundary).
- Type stubs for dynamic external APIs.

Forbidden in: function parameters, return types, variable annotations, generic parameters, names or aliases that hide typing.

### `object` Is Forbidden
Same prohibition as `Any`. If reaching for `object`, you likely need: a union type, a `Protocol`, a generic type parameter, or a Pydantic model.

### Built-in Generics (3.9+)
Use the built-in generic forms directly. Never import from `typing` for generic forms:
```python
list[str]          # not List[str]
dict[str, int]     # not Dict[str, int]
set[User]          # not Set[User]
tuple[int, str]    # not Tuple[int, str]
frozenset[str]     # not FrozenSet[str]
```

### Union Types (3.10+)
Use the pipe operator. Never use `Optional` or `Union`:
```python
str | None              # not Optional[str]
int | float | Decimal   # not Union[int, float, Decimal]
```

### Signature Complexity Threshold
Pydantic is required when:
- More than 2 union types in a single parameter
- Nested generics deeper than 2 levels
- More than 6 parameters in a public method

### `cast()` Is Forbidden
`cast()` lies to the type checker. Never cast to avoid errors. Fix the actual type mismatch, add proper annotations upstream, use type guards, or refactor.

### `if TYPE_CHECKING:` Is Absolutely Forbidden
**NEVER FUCKING USE `TYPE_CHECKING` IN PYTHON CODE — NO MATTER WHAT.**
Never use `TYPE_CHECKING` for import guards. It creates hidden import dependencies, breaks runtime introspection, and signals poor architecture. Restructure code to avoid circular imports. Use `Protocol` interfaces for dependency inversion.

### Variadic `*args`/`**kwargs` Are Forbidden
Forbidden in application code. The only exception is explicit API/framework adapter methods where the signature is dictated externally. When the exception applies:
- Arguments must be typed precisely (no `Any`/`object`).
- They must be converted into a Pydantic model immediately at the start of the method.
- A docstring "Rationale" section explains why alternatives do not work.

### `None` Identity Checks
Always use identity checks for `None`:
```python
# Correct
if x is None: ...
if x is not None: ...
# Wrong
if x == None: ...
if x != None: ...
```

### Linter Compliance Is Mandatory
When type checkers report errors, the code is wrong. Fix the code, not the tool.
- "Expected X, got Y" → fix the type mismatch
- "Incompatible return type" → fix return or declaration
- "Expression has type Any" → track source, add proper types
- `# type: ignore` is forbidden except with a linked issue explaining why

---
[Back to Overview](./OVERVIEW.md)
