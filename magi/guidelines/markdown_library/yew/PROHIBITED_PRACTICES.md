# Prohibited Practices

### Never Do

- `unwrap()` or `expect()` in app code.
- Side effects in render bodies.
- Keeping duplicated state that can be derived from props.
- Using unstable or non-unique keys in lists.
- Creating new closures on every render that capture non-changing deps (use `use_callback`).
- Allocating large `String`s repeatedly in `html!`; **memoize**.
- Blocking calls or `std::thread` usage; browser workers require different models.
- Non-ASCII characters in code.
- Placeholders, TODOs, incomplete blocks.
- `.await` in synchronous contexts.
- Direct `panic!()` calls in production code.
- Mutable global state without proper synchronization.
- Skipping shakedown after a triggering change.
- Running shakedown only in debug profile.
- Shakedown against `trunk serve` watch mode or a mocked backend.
- Treating `wasm-bindgen-test` alone as shakedown.

---
[Back to Overview](./OVERVIEW.md)
