# Logging, Telemetry, and Panics

```rust
fn main() {
    console_error_panic_hook::set_once();
    wasm_logger::init(wasm_logger::Config::new(log::Level::Debug)
        .module_prefix("my_app"));
    yew::Renderer::<App>::new().render();
}

// In components
log::info!("Component mounted: {}", component_name);
log::debug!("State updated: {:?}", new_state);
log::error!("API request failed: {}", error_msg);
```

### Rules

- Use `log` crate macros (`info!`, `warn!`, `error!`, `debug!`, `trace!`) **consistently**.
- **Never panic in production paths**; map errors to UI states.
- Consider adding client-side telemetry only with user consent.

---
[Back to Overview](./OVERVIEW.md)
