# Dependencies and Tooling

Minimal, stable set:

| Dependency | Version | Features |
|:-----------|:--------|:---------|
| `yew` | `0.21` | `csr` |
| `yew-router` | `0.18` | — |
| `gloo-net` | `0.6` | `http`, `websocket`, `eventsource`, `json` |
| `wasm-bindgen` | `0.2` | — |
| `wasm-logger` | `0.2` | — |
| `console_error_panic_hook` | `0.1` | — |
| `getrandom` (`wasm32` target) | `0.2` | `js` |

### Cargo.toml (ui)

```toml
[package]
name = "ui"
version = "0.1.0"
edition = "2024"
rust-version = "1.89.0"
publish = false

[dependencies]
yew = { version = "0.21", features = ["csr"] }
yew-router = "0.18"
gloo-net = { version = "0.6", features = ["http", "websocket", "eventsource", "json"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
wasm-bindgen = "0.2"
wasm-logger = "0.2"
log = "0.4"
console_error_panic_hook = "0.1"

[target.'cfg(target_arch = "wasm32")'.dependencies]
getrandom = { version = "0.2", features = ["js"] }

[profile.release]
opt-level = "s"
lto = true
codegen-units = 1
strip = true
panic = "abort"
```

### Trunk.toml

```toml
[serve]
address = "127.0.0.1"
port = 5173
open = false

[build]
dist = "dist"
public_url = "/"
filehash = true

[[hooks]]
stage = "pre_build"
command = "sh"
command_arguments = ["-c", "npm run build:css"]

# PostCSS processor for Tailwind (alternative to npm hook)
[[build.processors]]
type = "css"
target = "postcss"
mode = "pre-render"
source = ["src/style/tailwind.css"]
output = "dist/app.css"

[[proxy]]
rewrite = "/api/"
backend = "http://127.0.0.1:3000/"
ws = true

[watch]
ignore = ["target", "dist", "node_modules"]
```

### index.html

```html
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <title>OEE UI</title>
    <link data-trunk rel="css" href="/app.css" />
</head>
<body></body>
</html>
```

---
[Back to Overview](./OVERVIEW.md)
