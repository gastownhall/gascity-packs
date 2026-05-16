# Prohibited Practices

### Never Do
- Breaking lines unnecessarily when under 220 characters
- Multi-line function signatures that fit on one line
- Comments explaining obvious code
- Using `unwrap()`, `expect()`, or `panic!()` for recoverable errors
- Excessive vertical spacing
- Non-ASCII characters in identifiers
- Placeholders or TODOs in committed code
- Glob imports outside test modules
- `unsafe` without exhaustive safety documentation
- Blocking calls in async context
- `clone()` when borrowing suffices

### Always Do
- Maximize horizontal line usage up to 220 characters
- Keep function signatures on single lines when possible
- Use trailing commas in multi-line structures
- Propagate errors using `?`
- Prefer references over `clone()`
- Use `Arc` + `RwLock` over `Mutex` in async code
- Write self-explanatory code through naming
- Run `cargo clippy` and `cargo fmt` before committing
- Write tests for public interfaces
- Document public APIs

---
[Back to Overview](./OVERVIEW.md)
