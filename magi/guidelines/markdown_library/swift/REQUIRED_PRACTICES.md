# Required Practices

### Always Do

- Define explicit access control on all declarations.
- Specify `@MainActor` on view models and UI-bound state.
- Use `async`/`await` for new asynchronous code.
- Capture `[weak self]` in escaping closures and guard unwrap immediately.
- Provide default values for function parameters when sensible.
- Use Swift Package Manager for dependency management in new projects.
- Run `swiftformat` and `swiftlint` as pre-commit hooks or CI gates.
- Verify retain cycle freedom by checking `deinit` execution in development.
- Run a §21 shakedown after every triggering change before TestFlight/App Store submission.

---
[Back to Overview](./OVERVIEW.md)
