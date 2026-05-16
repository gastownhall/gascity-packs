# Defense in Depth

Multiple, independent layers protect Wicket framework code from a single failure. This is **failure-mode defense in depth** (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Seven Independent Layers of Defense

| Layer | Validation |
|:-----:|:-----------|
| 1 | **Typed models** — All `IModel` usages MUST be typed; raw `IModel` is forbidden |
| 2 | **WicketTester coverage** — MUST cover page rendering, form submission, and ajax behaviors |
| 3 | **Session discipline** — Stateless pages MUST be preferred where possible; stateful pages MUST justify their state |
| 4 | **End-to-end browser tests** — Selenium / Playwright MUST drive primary flows |
| 5 | **Ajax error paths** — Ajax error handlers MUST be implemented on every `AjaxBehavior` |
| 6 | **Performance and session monitoring** — Render time, session size, and 5xx rate MUST be alerted on |
| 7 | **Upgrade and dependency discipline** — Wicket and dependent libraries MUST be on supported versions; deprecated APIs MUST be migrated |

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority. Apply this rule whenever a decision in this domain depends on a check, a copy, a vote, or an actor that fails, drifts, or disagrees.

- **One is a claim** — A `WicketTester` pass is one signal; server-side rendering succeeded.
- **Two is a tie** — `WicketTester` + a manual click-through is two signals from non-automated paths and is fragile.
- **Three is a quorum** — `WicketTester` + browser-driven E2E + production telemetry form the triple. **All three MUST agree before declaring a feature done.**

**Example:** A form that submits successfully in `WicketTester` but the JavaScript-driven client validation breaks the browser submission — only the E2E layer catches it.

---
[Back to Overview](./OVERVIEW.md)
