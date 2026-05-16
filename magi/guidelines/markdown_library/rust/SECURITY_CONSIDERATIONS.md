# Security Considerations

### Input Validation
```rust
fn validate_username(s: &str) -> Result<&str, ValidationError> {
    if s.is_empty() { return Err(ValidationError::Empty); }
    if s.len() > 64 { return Err(ValidationError::TooLong); }
    if !s.chars().all(|c| c.is_alphanumeric() || c == '_') { return Err(ValidationError::InvalidChars); }
    Ok(s)
}
```

### Secret Handling
```rust
use secrecy::{ExposeSecret, Secret};
struct Credentials { username: String, password: Secret<String> }
impl Credentials {
    fn authenticate(&self) { let pw = self.password.expose_secret(); /* use pw */ }
}
```

### SQL Injection Prevention
Always use parameterized queries:
```rust
sqlx::query("SELECT * FROM users WHERE id = $1").bind(user_id).fetch_one(&pool).await?;
```

### Path Traversal Prevention
```rust
fn safe_path(base: &Path, user_input: &str) -> Result<PathBuf, Error> {
    let path = base.join(user_input).canonicalize()?;
    if !path.starts_with(base) { return Err(Error::PathTraversal); }
    Ok(path)
}
```

### Constant-Time Comparison
```rust
use subtle::ConstantTimeEq;
fn verify_token(provided: &[u8], expected: &[u8]) -> bool { provided.ct_eq(expected).into() }
```

---
[Back to Overview](./OVERVIEW.md)
