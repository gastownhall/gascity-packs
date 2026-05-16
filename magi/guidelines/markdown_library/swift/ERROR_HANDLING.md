# Error Handling

### Throwing Functions

- Use `throws` for recoverable errors where the caller can meaningfully respond.
- Use **typed throws** (`throws(MyError)`) when the error type is constrained and useful to callers (Swift 6+).
- Mark async throwing functions as `async throws`, not `throws async`.
- Document thrown error types in the function's documentation comment.

### Error Types

- Define **domain-specific error enums** conforming to `Error`.
- Include associated values for context: `case networkError(URLError)`, `case validationFailed(field: String, reason: String)`.
- Conform to `LocalizedError` and implement `errorDescription` for user-facing messages.
- **Avoid stringly-typed errors.** If you're throwing `NSError` with a message string, define an enum instead.

### Do-Catch Patterns

- Catch specific error types before falling back to generic catches.
- **Never use empty `catch {}` blocks.** Log, rethrow, or handle meaningfully.
- Use `try?` only when failure is truly ignorable and you don't need the error.
- Use `try!` exclusively in tests or when failure indicates programmer error (not runtime conditions).

### Result Type

- Use `Result<Success, Failure>` for async callbacks in pre-async/await codebases.
- Prefer `throws` over `Result` in modern Swift; `Result` is primarily for storage or bridging.
- Map and flatMap on `Result` to transform values without unpacking.

---
[Back to Overview](./OVERVIEW.md)
