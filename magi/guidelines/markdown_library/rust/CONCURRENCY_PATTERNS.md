# Concurrency Patterns

### Synchronization Primitives
```rust
use std::sync::Arc;
use tokio::sync::{RwLock, Mutex, mpsc, oneshot, broadcast, watch};

let shared_state = Arc::new(RwLock::new(State::default()));      // Prefer RwLock for read-heavy
let exclusive_state = Arc::new(Mutex::new(Resource::new()));     // Use Mutex only when needed
```

### Channel Selection
- **mpsc** — multiple producers, single consumer (task queues)
- **oneshot** — single value, single use (request/response)
- **broadcast** — multiple consumers, all receive (events)
- **watch** — single producer, latest value only (config updates)

### RwLock Patterns
```rust
let state = Arc::new(RwLock::new(State::default()));
let data = state.read().await.get_data().clone();   // Multiple concurrent readers
state.write().await.update_data(new_data);          // Exclusive write access
```

### Atomic Operations
```rust
use std::sync::atomic::{AtomicU64, AtomicBool, Ordering};
let counter = AtomicU64::new(0);
counter.fetch_add(1, Ordering::Relaxed);
let running = AtomicBool::new(true);
running.store(false, Ordering::SeqCst);
```

---
[Back to Overview](./OVERVIEW.md)
