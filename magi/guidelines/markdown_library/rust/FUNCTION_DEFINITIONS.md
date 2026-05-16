# Function Definitions

### Function Signatures
- **Always single-line** if under 220 characters (including all parameters, generics, where clauses, return types)
- Opening brace `{` on same line as signature
- Closing brace `}` on its own line for multi-line bodies

### Compact Functions
Write entire function on one line when it fits under 220 characters:
```rust
pub fn get_hostname(&self) -> &str { &self.hostname }
pub fn is_valid(&self) -> bool { self.status == Status::Valid }
pub fn format_uri(&self, path: &str) -> String { format!("{}/{}", self.hostname, path) }
pub const fn default_port() -> u16 { 8080 }
fn len(&self) -> usize { self.items.len() }
```

### Standard Functions
```rust
pub async fn provision_device(&self, device_id: &str, device_info: &Value) -> Result<Value, IoTHubError> {
    let url = self.format_uri(&format!("devices/{}", device_id));
    let response = self.client.put(&url).json(device_info).send().await?;
    response.json().await.map_err(Into::into)
}
```

### Multi-line Signatures (Only When Exceeding 220 Characters)
```rust
pub async fn extremely_long_function_name_with_many_parameters(
    param1: &VeryLongTypeName,
    param2: &AnotherVeryLongTypeName,
    param3: ComplexGenericType<T, U>,
    param4: &str,
) -> Result<ComplicatedReturnType, DetailedErrorType> {
    // Implementation
}
```

### Function Ordering Within impl Blocks
1. Associated constants
2. Constructors (`new`, `default`, `from_*`, `with_*`)
3. Getters (immutable access)
4. Setters (mutable access)
5. Conversion methods (`into_*`, `as_*`, `to_*`)
6. Action methods (business logic)
7. Private helper methods

---
[Back to Overview](./OVERVIEW.md)
