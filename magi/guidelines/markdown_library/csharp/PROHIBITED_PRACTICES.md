# Prohibited Practices

### Never Do

- Block on async code (`.Result`, `.Wait()`, `.GetAwaiter().GetResult()`) except in `Main` entry points
- Use `async void` except for event handlers
- Swallow exceptions with empty catch blocks
- Use exceptions for control flow
- Ignore `CancellationToken` in async I/O methods
- Use `var` when the type isn't obvious from the right-hand side
- Use string concatenation in loops (use `StringBuilder`)
- Use `DateTime.Now` instead of `DateTime.UtcNow` or `DateTimeOffset`
- Perform culture-sensitive string operations without explicit `StringComparison`
- Use `GC.Collect()` in application code
- Use `#region` blocks except for generated code
- Commit code with TODO, FIXME, or placeholder comments
- Use service locator pattern; inject dependencies through constructors
- Store secrets in configuration files or source control
- Use mutable statics for shared state
- Ignore compiler warnings; treat warnings as errors
- Remove code unnecessarily (ex. unused code)
- Modify code to be "simpler" and remove key features and/or functionality
- Use `NotImplementedException`
- Downgrade packages or .NET version
- Run shakedown against mocked dependencies or skip after DI graph changes

### Always Do

- Enable nullable reference types and treat null warnings as errors
- Use `sealed` on classes not designed for inheritance
- Accept `CancellationToken` in async methods performing I/O
- Use `ConfigureAwait(false)` in library code
- Validate inputs at public API boundaries
- Use structured logging with message templates
- Use `IReadOnlyList<T>` and `IReadOnlyDictionary<K,V>` for return types
- Dispose resources using `using` declarations
- Use primary constructors for DI in simple services
- Use records for DTOs, events, and value objects
- Pin package versions centrally
- Configure analyzers and treat warnings as errors
- Test edge cases and failure scenarios
- Document public APIs with XML documentation
- Follow code formatting, removing extraneous comments **WITHOUT** removing comments that indicate TODO, incomplete, etc.
- Be intentional about the code you implement
- Implement **ANY AND ALL** outstanding, unimplemented, TODO, etc... code **PROPERLY AND CORRECTLY**
- Run shakedown after every trigger condition in §24

---
[Back to Overview](./OVERVIEW.md)
