# Build, Optimize, and Serve

### Dev

`trunk serve` on `127.0.0.1:5173` with API proxy to `127.0.0.1:3000`.

### Production

`trunk build --release` produces `ui/dist`. Serve with `axum` using `tower_http` `ServeDir` and `ServeFile` fallback to `index.html`.

```rust
use axum::{Router, routing::get_service};
use tower_http::services::{ServeDir, ServeFile};
use std::path::PathBuf;

fn mount_spa(api: Router) -> Router {
    let assets: PathBuf = ["ui", "dist"].iter().collect();
    let spa = get_service(ServeDir::new(&assets).fallback(ServeFile::new(assets.join("index.html"))));
    Router::new().nest("/api", api).nest_service("/", spa)
}
```

### Optimizations

- Install `binaryen` (`wasm-opt`) and keep `data-wasm-opt="z"`.
- Ensure release profile uses `opt-level="s"`, `lto=true`, `codegen-units=1`, `strip=true`, `panic="abort"`.

```toml
# Cargo.toml
[profile.release]
opt-level = "s"     # Optimize for size
lto = true          # Link-time optimization
codegen-units = 1   # Single codegen unit
strip = true        # Strip symbols
panic = "abort"     # Smaller panic handler

[profile.wasm-release]
inherits = "release"
opt-level = "z"     # Aggressive size optimization
```

```toml
# .cargo/config.toml
[build]
target = "wasm32-unknown-unknown"

[target.wasm32-unknown-unknown]
rustflags = [
    "-C", "link-arg=--no-entry",
    "-C", "link-arg=--export-dynamic",
]
```

---
[Back to Overview](./OVERVIEW.md)
