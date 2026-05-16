# Defense in Depth

Multiple, independent layers protect Yew (Rust/WASM) code from a single failure. This is **failure-mode defense in depth** (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Six Independent Layers of Defense

| Layer | Validation |
|:-----:|:-----------|
| 1 | **Compiler strictness** — Crate-wide `deny(warnings)` MUST hold. Rust compiler is layer one |
| 2 | **Clippy** — `cargo clippy --all-targets --all-features` with `-D warnings` MUST pass |
| 3 | **wasm-pack tests** — `wasm-pack test --headless` (chrome/firefox) MUST run integration tests **in a real browser, not just node** |
| 4 | **Trunk build validation** — `trunk build --release` MUST succeed and produce expected hashes. CI re-runs this on a clean agent |
| 5 | **E2E browser tests** — Playwright/Selenium MUST drive the live WASM bundle on the deployed preview |
| 6 | **Runtime validation** — Server responses parsed in WASM MUST be validated with serde + explicit error variants; **never `expect()`** |

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority. Apply this rule whenever a decision in this domain depends on a check, a copy, a vote, or an actor that fails, drifts, or disagrees.

- **One is a claim** — A green `cargo build` is one signal; **WASM-specific failures (panic abort, allocator, web-sys binding mismatch) are invisible at compile time**.
- **Two is a tie** — Native tests passing but headless-browser tests failing is the platform-difference dissent; **the browser run wins**.
- **Three is a quorum** — Compiler + clippy + browser-driven WASM tests form the triple. **All three MUST agree before declaring a Yew change done.**

**Example:** A function that compiles, lints clean, and passes native tests still panics in WASM because of an unsupported syscall; **the browser test is the third — and decisive — voter**.

---
[Back to Overview](./OVERVIEW.md)
