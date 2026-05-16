# Troubleshooting Guide

- **"borrowed value does not live long enough"**: Reference outlives data. Solutions: return owned data, use `'static`, clone, or restructure ownership.
- **"cannot borrow as mutable because it is also borrowed as immutable"**: Violates borrowing rules. Solutions: limit borrow scope, use interior mutability (`RefCell`, `RwLock`), or clone.
- **"future cannot be sent between threads safely"**: Async task holds non-Send data. Solutions: use `Arc<Mutex<T>>` instead of `Rc<RefCell<T>>`, drop guards before `.await`, or use `spawn_local`.
- **"implementation of trait is not general enough"**: Higher-ranked trait bound issue. Solutions: add explicit lifetimes, use `for<'a>` syntax, or box with `dyn Trait`.
- **"overflow evaluating requirement"**: Recursive type without indirection. Solutions: add `Box<T>`, use `Rc<T>`/`Arc<T>`, or use arena allocation.
- **Deadlocks in async code**: Causes: holding mutex across `.await`, circular locks, blocking in async context. Solutions: use async-aware locks (`tokio::sync`), never hold locks across await points, use lock ordering.
- **Performance regression**: Causes: unnecessary allocations, excessive cloning, lock contention, sync in async context. Debug: use `cargo flamegraph`, check allocations with `dhat`, review lock patterns.

---
[Back to Overview](./OVERVIEW.md)
