# Prohibited Practices

### Never Do

- Force unwrap (`!`) in production code outside framework-guaranteed contexts.
- Use `try!` for operations that can fail at runtime.
- Swallow errors with empty `catch {}` blocks.
- Use `Any` or `AnyObject` when concrete types or protocols are feasible.
- Create retain cycles through strong delegate references or unguarded closure captures.
- Block the main thread with synchronous network calls or heavy computation.
- Use `Thread` or `DispatchQueue` in new code when Swift Concurrency applies.
- Commit code with `// TODO` or `// FIXME` markers lacking issue references.
- Use Objective-C runtime features (`@objc`, `dynamic`) without explicit justification.
- Rely on implicit `self` in closure captures; always specify capture semantics.
- Leave unused imports, parameters, or variables in committed code.
- Use `class` when `struct` or `actor` satisfies requirements.
- Use `open` access control without documented subclassing contracts.
- Skip the §21 shakedown after a triggering change.
- Run shakedown against `URLProtocol` stubs, Mockingbird doubles, or any non-real backend.
- Write shakedown artifacts to `NSTemporaryDirectory()`, `/tmp`, or system temp.

---
[Back to Overview](./OVERVIEW.md)
