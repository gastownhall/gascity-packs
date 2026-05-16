# Scripting Changes

| Component | Change |
|:----------|:-------|
| `ScriptFunctionDocProvider` | Revamped with rich `CompletionDescriptor` objects |
| `PropertiesFileDocProvider` | Revamped backwards-compatibly |
| `@JythonElement` | New annotation for static fields and constants — replaces `@ScriptFunction` for those use cases |
| `@ScriptFunction` | Retained for methods |
| `ScriptContext` | Revamped — affects modules creating their own scripting execution contexts (e.g., extension function style scripts) |

---
[Back to Overview](./OVERVIEW.md)
