# Comprehensive Yew (Rust/WASM) Development Library

**Runtime:** Yew 0.21+, Rust 1.89.0+, Edition 2024.

Authoritative reference for Rust/Yew WebAssembly application development. Optimizes for horizontal density and clean diffs (220 char hard limit), predictable rendering and minimal allocations in hot paths, clear stable data flow from parents to children, **zero panics in production** (no `unwrap`/`expect` in app code), Rust edition 2024 / 1.89.0 compatibility.

## Critical Mandates (Read First)

- **Zero unwrap / expect in application code — no exceptions.** Never use `unwrap()` or `expect()` in production paths.
- **220 character hard line limit.** Maximum line length is 220 characters.
- **Horizontal density.** Prefer compact single-line expressions when readable.
- **Zero panics in production.** All errors must be handled gracefully — map to UI states, never panic in user-facing code.
- **Shakedown Required** — Real Chromium against real backend on both debug and release profiles after every triggering change.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [Project Structure](./PROJECT_STRUCTURE.md)
3. [Dependencies and Tooling](./DEPENDENCIES.md)
4. [Component Conventions](./COMPONENTS.md)
5. [Props and Data Flow](./PROPS.md)
6. [State Management and Hooks](./STATE_HOOKS.md)
7. [Events and Callbacks](./EVENTS.md)
8. [Rendering and Templates](./RENDERING.md)
9. [Lists, Keys, and Conditional Rendering](./LISTS.md)
10. [Async, Effects, and Data Fetching](./ASYNC.md)
11. [Networking: HTTP, WebSocket, SSE](./NETWORKING.md)
12. [Routing](./ROUTING.md)
13. [Error Handling and UX States](./ERROR_HANDLING.md)
14. [Performance and Memoization](./PERFORMANCE.md)
15. [HTML, CSS, and Assets](./HTML_CSS.md)
16. [Interop (wasm-bindgen / web-sys)](./INTEROP.md)
17. [Web Workers and Agents](./WORKERS.md)
18. [Testing](./TESTING.md)
19. [Logging, Telemetry, and Panics](./LOGGING.md)
20. [Build, Optimize, and Serve](./BUILD.md)
21. [Shakedown — Integration Validation](./SHAKEDOWN.md)
22. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
23. [Reusable Patterns](./REUSABLE_PATTERNS.md)
24. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
25. [Required Practices](./REQUIRED_PRACTICES.md)
26. [Style Summary](./STYLE_SUMMARY.md)
