# Defense in Depth

Multiple, independent layers protect Swift code from a single failure. This is **failure-mode defense in depth** (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Strict concurrency** — Strict concurrency checking MUST be enabled. Data-race bugs in Swift are silent in production; the compiler is layer one.
2. **swiftlint and swift-format** — Both MUST pass with **zero warnings**.
3. **XCTest suite** — Unit + UI tests MUST cover view models, services, primary user flows.
4. **Instruments profiling** — Allocations, Time Profiler, Leaks runs MUST be performed before any release. Performance regressions are functional regressions on mobile.
5. **CI build on clean simulator** — CI MUST build and test on a clean simulator image to avoid local cache masking failures.
6. **Crash reporting** — Crashlytics, AppCenter, Sentry, or App Store Connect MUST surface every production exception.
7. **Shakedown** — A §21 shakedown MUST pass after every triggering change before TestFlight/App Store submission.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority. Apply this rule to release readiness.

- **One is a claim** — An app that runs in the simulator is one signal; it has not been validated on a physical device or under low-memory conditions.
- **Two is a tie** — If unit tests pass but UI tests fail, the build is **NOT** shippable. Two disagreeing test suites require a third (manual smoke run on device) before release.
- **Three is a quorum** — Unit tests + UI tests + crash-reporting telemetry form the triple. **Majority MUST agree the build is healthy** before submission.

**Example:** A build that crashes on launch on iPhone 12 but runs on the simulator and on iPhone 15 is the third vote outweighing the first two — block release.

---
[Back to Overview](./OVERVIEW.md)
