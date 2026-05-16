# Shakedown — Integration Validation

### Definition

A Yew shakedown is the **post-build integration smoke for a Yew/WASM frontend**. It loads the generated `.wasm` bundle in a real browser against a real backend and validates that **wasm instantiation, JS interop, DOM bindings, fetch round-trip, router navigation, and component lifecycle all succeed as an integrated whole**. **It is not `cargo test`, not `wasm-bindgen-test` in a headless runner alone, and not `trunk serve`.** It sits between preflight (cargo check, wasm-pack build or trunk build completes, `Cargo.lock` intact, `wasm-opt` present) and production testing (load tests, visual regression, end-to-end user flows).

### Mandatory Triggers

Run shakedown after:

- The first successful `wasm-pack build` or `trunk build` of a new UI crate.
- Any bump to `yew`, `yew-router`, `wasm-bindgen`, `web-sys`, `js-sys`, `gloo-net`, or `reqwasm`.
- Any Rust edition or toolchain change.
- Any change to the panic hook or `wasm-logger` init.
- Any change to the `Trunk.toml` build or proxy configuration.
- Any change to the release profile (`opt-level`, `lto`, `codegen-units`, `panic` strategy).
- Any refactor that alters a `#[function_component]` Props boundary or the `yew-router` `Route` enum.

**Run shakedown on both the debug profile and the release profile** — release-mode optimizations (`lto=true`, `codegen-units=1`, `opt-level=s` or `z`, `strip=true`) reveal panics, dead-code elimination of JS interop shims, and wasm-bindgen binding failures that are silently absent in debug. **A debug-only shakedown pass is not a shakedown.**

### Non-Triggers

- Content-only `html! { }` text node edits.
- Tailwind class tweaks that do not introduce new `classes!()` composition.
- Documentation comments in Rust source.
- Test-only file edits under `#[cfg(test)]`.
- `cargo fmt` cosmetic changes.

### Validation Categories

Shakedown proves:

| # | Surface | What is verified |
|:-:|:--------|:-----------------|
| 1 | **WASM instantiation** | The `.wasm` bundle instantiates without a wasm instantiation error and without tripping `console_error_panic_hook` — **any Rust panic surfacing as a `JsValue` in the browser console is a fail-blocking condition** |
| 2 | **JS imports** | `wasm-bindgen` generated glue resolves every imported JS function — missing imports appear as "imported function 'X' is not defined" at instantiation |
| 3 | **DOM bindings** | gloo / `web_sys` DOM bindings mount the root node and react to at least one event (`onclick` or `oninput`) **from the real DOM, not from a simulated event** |
| 4 | **Fetch round-trip** | A real fetch (`gloo_net::http::Request` or `reqwasm::http::Request`) completes against the staging backend, deserializes with serde, and updates a `UseStateHandle` driving a rendered `Html` |
| 5 | **Router navigation** | `yew-router` navigation through `BrowserRouter` / `Switch` renders each representative route and the `NotFound` route without remounting errors |
| 6 | **Lifecycle cleanup** | Component mount/unmount cleanly invokes `use_effect_with` cleanup closures, with **no leaked subscriptions** and **no `web_sys::Closure` instances retained after unmount** |
| 7 | **Props diffing** | `#[derive(Properties, PartialEq)]` Props are correctly resolved and diff-compared across at least one parent re-render — **a broken `PartialEq` manifests as either infinite re-render or missed updates** |
| 8 | **Release profile parity** | In release profile, the bundle survives the same path with `lto`/`opt-level=s`/`strip=true` active, **proving no binding or panic-hook wiring was optimized away** |

### Execution Principles

- **Conservative inputs only** — known-good backend fixtures, one representative authenticated user, one representative dataset.
- **Progressive stress** — Start with `BrowserRouter` mounting the index route; add one navigation; then one fetch; then one form submission. **Stop at the first failure and diagnose.**
- **Controlled environment** — A real Chromium (headless Playwright or `wasm-bindgen-test` with `--chromedriver`) and a real staging backend on loopback or in an isolated network.
- **Observable execution** — `wasm_logger` initialized at `Level::Debug` during shakedown (not release-default `Level::Warn`), browser console fully captured, every panic routed through `console_error_panic_hook` so stack traces surface in the capture.
- **Known-good inputs** — Inputs whose expected DOM output is documented in the shakedown fixture.
- **No optimization during shakedown** — Note performance issues and move on; **shakedown validates correctness, not bundle size or first-paint time**.

### Execution Pattern

1. Confirm preflight passes (`cargo check` clean, `wasm-pack build` or `trunk build --release` clean, `Trunk.toml` valid, backend reachable).
2. Serve the `dist/` artifact from a real HTTP server (**not `trunk serve` in watch mode**).
3. Launch headless Chromium at the artifact URL.
4. Assert the root Yew app mounts and the index route renders the expected shell sentinel.
5. Verify the browser console contains **zero error-level entries** and **zero "imported function not defined" warnings**.
6. Execute one fetch round-trip and assert the rendered DOM reflects the deserialized payload.
7. Navigate through each representative route via `yew-router` `Link`.
8. Trigger one unmount (navigate to NotFound, then back) and inspect that `use_effect_with` cleanup ran (no duplicate listeners, no `Closure` leaks).
9. Repeat the full sequence against the **release-profile artifact**.
10. Record observations.
11. Classify results.

### Reference Shakedown Harness

Minimal harness invoked from the UI crate to instantiate the root app, trigger one fetch round-trip, and assert a rendered sentinel before any user traffic.

```rust
use yew::prelude::*;
use wasm_bindgen::prelude::*;
use wasm_bindgen_futures::spawn_local;
use gloo_net::http::Request;

#[derive(Clone, PartialEq, serde::Deserialize)]
struct ShakedownPayload { ok: bool, sentinel: String }

#[function_component(ShakedownRoot)]
fn shakedown_root() -> Html {
    let state = use_state(|| None::<ShakedownPayload>);
    {
        let state = state.clone();
        use_effect_with((), move |_| {
            spawn_local(async move {
                match Request::get("/api/__shakedown__").send().await {
                    Ok(resp) => match resp.json::<ShakedownPayload>().await {
                        Ok(payload) => state.set(Some(payload)),
                        Err(e) => log::error!("shakedown deserialize failed: {e}"),
                    },
                    Err(e) => log::error!("shakedown fetch failed: {e}"),
                }
            });
            || ()
        });
    }
    match &*state {
        None => html! { <div id="shakedown-pending">{"shakedown pending"}</div> },
        Some(p) if p.ok => html! { <div id="shakedown-ok">{&p.sentinel}</div> },
        Some(_) => html! { <div id="shakedown-fail">{"shakedown fail"}</div> },
    }
}

#[wasm_bindgen(start)]
pub fn shakedown_start() {
    console_error_panic_hook::set_once();
    wasm_logger::init(wasm_logger::Config::new(log::Level::Debug));
    yew::Renderer::<ShakedownRoot>::new().render();
}
```

### Result Classification

| Outcome | Trigger |
|:--------|:--------|
| **Pass** | wasm instantiates, DOM mounts, fetch round-trip completes, routes render, lifecycle cleans up, **zero console errors**, both debug and release profiles green |
| **Fail-blocking** | Any Rust panic in the console, any wasm instantiation failure, any missing JS import, any failed fetch deserialization, any hydration/mount failure, any leaked `Closure` or duplicate event listener after unmount, **any release-profile regression versus debug**. Fix the code and re-run from step one |
| **Fail-nonblocking** | Non-critical deprecation warnings from `web_sys` or `wasm-bindgen` that do not break behavior; bundle size anomalies. Log to issue tracker and proceed |
| **Inconclusive** | Staging backend unreachable, Chromium launch failure, artifact server misconfiguration. Repair the environment and re-run the affected validation only |

### Required Artifacts

- **Browser console capture** — Full capture with stack traces for any panic routed through `console_error_panic_hook`.
- **Result summary** — Per validation category for **both debug and release profiles**.
- **Issue list** — Every anomaly classified blocking / non-blocking / inconclusive with a reproduction recipe.
- **Environment snapshot** — Pinning `rustc` version, `wasm-bindgen` version, `yew` version, `yew-router` version, `gloo-net` version, Trunk version, **the exact `.wasm` bundle hash**, the Chromium version, the backend commit SHA.

**A Yew shakedown without these four artifacts is not a shakedown** and the artifact is not eligible for promotion.

### Anti-Patterns

- Treating `wasm-bindgen-test` alone as shakedown. It does not exercise the real HTTP proxy, the real router mount sequence, or the release-profile artifact.
- Shakedown against `trunk serve` in watch mode. **Hot reload masks lifecycle bugs.**
- Shakedown in jsdom or any non-Chromium shim environment.
- Shakedown against a mocked fetch backend.
- Shakedown only in debug profile.
- Optimization during shakedown.
- Skipping shakedown after a `wasm-bindgen` or `web-sys` version bump because "it compiled".
- Declaring success without capturing the browser console.

---
[Back to Overview](./OVERVIEW.md)
