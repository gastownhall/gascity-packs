# Structural Elements

### Parentheses Content Rule
Everything between `(` and `)` stays on one line unless exceeding 220 characters:
```rust
let result = complex_function(arg1, arg2, arg3, arg4, arg5, arg6);
let response = client.post(&url).header(AUTHORIZATION, format!("SharedAccessSignature {}", sas_token)).json(&obj).send().await?;
let config = (hostname.to_string(), port, timeout_seconds, retry_count, use_tls);
```

### Struct Definitions
**Compact** (when simple and fits):
```rust
pub struct Point { pub x: i32, pub y: i32 }
struct Pair<T>(T, T);
```
**Standard** (for complex structures):
```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    pub hostname: String,
    pub port: u16,
    #[serde(default = "default_timeout")]
    pub timeout: Duration,
    pub retry_count: u32,
}
```

### Struct Literals
**Compact** (when fits):
```rust
let point = Point { x: 10, y: 20 };
let config = Config { hostname: host.into(), port: 8080, timeout: Duration::from_secs(30), retry_count: 3 };
```
**Multi-line** (for complex initializations):
```rust
let config = Config {
    hostname: env::var("HOST").unwrap_or_else(|_| "localhost".to_string()),
    port: env::var("PORT").ok().and_then(|p| p.parse().ok()).unwrap_or(8080),
    timeout: Duration::from_secs(30),
    retry_count: 3,
};
```

### Enum Definitions
```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Status { Pending, Active, Completed, Failed }

#[derive(Debug, thiserror::Error)]
pub enum AppError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("Parse error at line {line}: {message}")]
    Parse { line: usize, message: String },
    #[error("Not found: {0}")]
    NotFound(String),
}
```

### Arrays and Vectors
**Single-line** when fitting:
```rust
let ports = [8080, 8081, 8082, 8083, 8084];
let data = vec![1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
let names: Vec<&str> = vec!["alpha", "beta", "gamma", "delta"];
```
**Multi-line** for large data or complex elements:
```rust
let matrix = [
    [1, 2, 3],
    [4, 5, 6],
    [7, 8, 9],
];
let handlers: Vec<Box<dyn Handler>> = vec![
    Box::new(AuthHandler::new()),
    Box::new(LoggingHandler::new()),
    Box::new(RateLimitHandler::new()),
];
```

---
[Back to Overview](./OVERVIEW.md)
