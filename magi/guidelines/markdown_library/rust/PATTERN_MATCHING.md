# Pattern Matching

### Compact Match (Default)
Single-line arms when they fit:
```rust
let code = match status { Status::Ok => 200, Status::NotFound => 404, Status::Error => 500, _ => 400 };
let level = match severity { 0..=2 => "low", 3..=5 => "medium", _ => "high" };
```

### Standard Match
```rust
match result {
    Ok(data) => process(data),
    Err(e) if e.is_retriable() => retry(e),
    Err(e) => return Err(e),
}
```

### Multi-line Match Arms
Only for complex logic requiring multiple statements:
```rust
match message {
    Message::Request { id, payload } => {
        let response = process_request(id, payload).await?;
        send_response(id, response).await?;
    },
    Message::Response { id, data } => {
        handle_response(id, data)?;
    },
}
```

### Destructuring Patterns
```rust
let Point { x, y } = point;
let (first, second, rest @ ..) = tuple;
let Config { hostname, port, .. } = config;
if let Some(Value::Object(map)) = json.get("data") { process_map(map); }
```

### Match Guards
```rust
match value {
    n if n < 0 => handle_negative(n),
    n if n > 100 => handle_large(n),
    n => handle_normal(n),
}
```

### `matches!` Macro for Boolean Checks
```rust
let is_success = matches!(response.status(), StatusCode::OK | StatusCode::CREATED);
let is_whitespace = matches!(c, ' ' | '\t' | '\n' | '\r');
```

---
[Back to Overview](./OVERVIEW.md)
