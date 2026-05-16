# Comments and Documentation

### Comments
- **Avoid entirely** — code should be self-explanatory
- Use descriptive naming instead of comments
- Only use when absolutely critical for understanding non-obvious behavior

### Documentation Comments
```rust
/// Generates a SAS token for Azure IoT Hub authentication.
///
/// # Arguments
/// * `target_uri` - The resource URI to authenticate against
/// * `expiry` - Token expiration time as Unix timestamp
///
/// # Example
/// ```
/// let token = client.generate_sas_token("https://hub.azure.net", 3600)?;
/// ```
pub fn generate_sas_token(&self, target_uri: &str, expiry: u64) -> Result<String, IoTHubError> { /* ... */ }
```

### Module-Level Documentation
```rust
//! # Configuration Module
//! Provides configuration loading and validation for the application.
```

### Documentation Rules
- Document all public items with examples
- Document panics, errors, and safety requirements
- Keep examples compilable (`cargo test --doc`)

---
[Back to Overview](./OVERVIEW.md)
