# Logging and Diagnostics

### Logging Setup
Use `tracing` for structured logging:
```rust
use tracing::{debug, error, info, instrument, warn};
use tracing_subscriber::{fmt, prelude::*, EnvFilter};

fn init_logging() {
    tracing_subscriber::registry().with(fmt::layer()).with(EnvFilter::from_default_env()).init();
}
```

### Log Levels
- `error!` — failures requiring immediate attention
- `warn!` — unexpected but recoverable situations
- `info!` — significant state changes
- `debug!` — detailed flow information
- `trace!` — very detailed diagnostics

### Structured Logging
```rust
info!(user_id = %user.id, action = "login", "User logged in");
error!(error = ?e, path = %path.display(), "Failed to read file");
debug!(request_id = %id, duration_ms = elapsed.as_millis(), "Request completed");
```

### Instrumentation
```rust
#[instrument(skip(self, password), fields(user_id = %user_id))]
pub async fn authenticate(&self, user_id: &str, password: &str) -> Result<Token, AuthError> {
    info!("Authentication attempt");
    self.verify_credentials(user_id, password).await
}
```

---
[Back to Overview](./OVERVIEW.md)
