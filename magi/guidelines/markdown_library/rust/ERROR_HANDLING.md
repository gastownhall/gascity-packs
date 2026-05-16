# Error Handling

### Core Philosophy
- **All errors are values** — use `Result<T, E>` universally
- **Errors propagate** — use `?` operator
- **Errors are typed** — custom error enums for each domain

### Propagation with `?`
```rust
pub fn read_config(path: &Path) -> Result<Config, ConfigError> {
    let content = fs::read_to_string(path)?;
    let config: Config = serde_json::from_str(&content)?;
    Ok(config)
}
```

### Compact Error Handling
```rust
let key = STANDARD.decode(&self.shared_access_key).map_err(|e| IoTHubError::AuthError(format!("Failed to decode: {}", e)))?;
let port = env::var("PORT").ok().and_then(|p| p.parse().ok()).unwrap_or(8080);
```

### Custom Error Types
Use `thiserror` for library errors:
```rust
#[derive(Debug, thiserror::Error)]
pub enum ServiceError {
    #[error("Connection failed: {0}")]
    Connection(#[from] std::io::Error),
    #[error("Authentication failed for user {user}: {reason}")]
    Auth { user: String, reason: String },
    #[error("Resource not found: {0}")]
    NotFound(String),
}
```
Use `anyhow` for applications:
```rust
use anyhow::{Context, Result};
pub fn process_file(path: &Path) -> Result<Data> {
    let content = fs::read_to_string(path).with_context(|| format!("Failed to read: {}", path.display()))?;
    serde_json::from_str(&content).context("Failed to parse JSON")
}
```

### Never Use in Production
- `unwrap()` — panics on None/Err
- `expect()` — panics with message
- `panic!()` — except for truly unrecoverable states

---
[Back to Overview](./OVERVIEW.md)
