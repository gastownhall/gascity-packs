# Style Summary

| Element                 | Required Style                                |
|-------------------------|-----------------------------------------------|
| **Line Length**         | Maximum 220 characters                        |
| **Function Signatures** | Single-line unless exceeding limit            |
| **Parentheses Content** | Everything between `()` on one line           |
| **Imports**             | Single-line per module unless exceeding limit |
| **Simple Functions**    | Entire function on one line when fits         |
| **Error Handling**      | Inline with `?`, never `unwrap()`             |
| **Method Chains**       | Single-line when possible                     |
| **Match Expressions**   | Compact single-line arms when simple          |
| **Conditionals**        | Inline for simple cases                       |
| **Comments**            | Avoid entirely                                |
| **Documentation**       | Required for all public items                 |
| **Indentation**         | 4 spaces                                      |
| **Trailing Commas**     | Required in multi-line structures             |
| **Braces**              | Opening on same line, closing on own line     |
| **Testing**             | Required for public interfaces                |
| **Logging**             | Use `tracing` with structured fields          |
| **Concurrency**         | Prefer `RwLock` over `Mutex` in async         |

---
[Back to Overview](./OVERVIEW.md)
