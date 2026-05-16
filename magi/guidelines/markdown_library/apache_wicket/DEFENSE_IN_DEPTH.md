# Defense in Depth

Multiple, independent layers protect Apache Wicket applications from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Compile-time safety** — Components MUST use typed models (`IModel<T>`); raw `Object` models are forbidden.
2. **Automated tests with `WicketTester`** — MUST cover every page and panel; manual click-through is not enough.
3. **Page and component versioning** — Stateful pages MUST have explicit page-versioning policies; back-button bugs are a class of Wicket regression.
4. **Session-size monitoring** — Session size MUST be monitored; runaway sessions kill memory.
5. **AJAX request error logging** — Ajax behaviors MUST handle errors and surface them; silent AJAX failures are invisible.
6. **End-to-end tests** — Selenium or Playwright MUST exercise primary flows against the running app.
7. **Structured logs and metrics** — Page-render time and 5xx rate MUST be alerted on.
8. **Shakedown** — §16 covers integration paths the unit suite cannot.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — A passing `WicketTester` test is one signal. It does NOT prove the rendered HTML behaves in the browser.
- **Two is a tie** — `WicketTester` pass + manual click-through OK but Selenium failing is the rendering dissent. The browser wins.
- **Three is a quorum** — `WicketTester` + Selenium + production telemetry (page-render time, error rate) form the triple. All three MUST agree before declaring a Wicket change done.

Example: A panel that passes `WicketTester` but throws in production from an unbounded recursive component tree — only telemetry catches it after release; a Selenium soak test is the layer that catches it before.

---
[Back to Overview](./OVERVIEW.md)
