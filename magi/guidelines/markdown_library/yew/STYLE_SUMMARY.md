# Style Summary

| Element | Required pattern |
|:--------|:-----------------|
| **Line Length** | Maximum 220 chars |
| **Component Definition** | Function components, single-line bodies when possible |
| **Props** | `#[derive(Properties, PartialEq)]`; `AttrValue` for strings; `Rc` for large data |
| **State** | `use_state` / `use_reducer`; derive values via `use_memo` |
| **Events** | `use_callback` for stable handlers; no async in render |
| **Networking** | `gloo-net` for HTTP/WS/SSE; map errors, no unwrap |
| **Lists** | Always set `key` with stable unique ID |
| **Routing** | `yew-router` with `NotFound` route; server fallback to `index.html` |
| **Error Handling** | Result mapping to UI states; never panic in user paths; `LoadState<T>` enum pattern |
| **Performance** | Avoid clones in render; use `Rc` / `AttrValue`; memoize derived data |
| **CSS / Assets** | `classes!` / `class="..."` usage; Trunk for copy/css; Tailwind via PostCSS or Stylist for CSS-in-Rust |
| **Interop** | Minimal `wasm-bindgen` / `web-sys`; non-blocking |
| **Workers** | `#[reactor]` agents for heavy background processing |
| **Testing** | Unit-test logic; keep DOM tests minimal; `wasm-bindgen-test` for in-browser checks |
| **Build / Serve** | `trunk serve` for dev; `trunk build --release` for prod; `tower_http` `ServeDir` + `ServeFile` fallback |
| **Trailing Commas** | Required in multi-line structures and match arms |
| **Braces** | Opening brace on same line; closing brace on own line |
| **Shakedown** | Real Chromium against real backend; both debug and release profiles; eight validation categories; four required artifacts |
| **Defense in Depth** | Compiler + clippy + wasm-pack browser tests + trunk release build + Playwright/Selenium + serde runtime validation = six independent layers; compiler + clippy + browser-driven WASM tests = the Rule of Three quorum |

---

Following this guide yields Yew code that is **horizontally dense, predictable to reason about, cheap to re-render, and production-ready**.

**Apply these rules uniformly to all files in the `ui` crate and to any shared component modules across the workspace.**

---
[Back to Overview](./OVERVIEW.md)
