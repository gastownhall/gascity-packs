# Method Chaining

### Compact Chaining (Default)
Keep chains on one line if under 220 characters:
```rust
let result = input.trim().to_lowercase().replace(" ", "_").parse::<u32>().unwrap_or(0);
let items: Vec<_> = data.iter().filter(|x| x.is_valid()).map(|x| x.transform()).collect();
let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("unknown");
```

### Multi-line Chaining (When Necessary)
Each method on new line, starting with `.`:
```rust
let stream = llm_stream
    .map(|chunk| chunk.to_string())
    .filter(|s| !s.is_empty())
    .take_while(|s| s != "DONE")
    .chain(futures::stream::once(async { Ok("done".to_string()) }));
```

### Builder Pattern Chaining
```rust
let client = ClientBuilder::new()
    .timeout(Duration::from_secs(30))
    .connect_timeout(Duration::from_secs(10))
    .pool_max_idle_per_host(10)
    .build()?;
```

---
[Back to Overview](./OVERVIEW.md)
