# Defense in Depth

Multiple, independent layers protect C#/.NET code from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Nullable reference types** — Enabled for every project. Null-deref is the most common .NET bug; the compiler kills it at layer one.
2. **`TreatWarningsAsErrors`** — `TreatWarningsAsErrors` plus Roslyn analyzers (StyleCop, FxCop, NetAnalyzers) MUST run during build.
3. **xUnit tests** — Unit tests MUST cover business logic; integration tests MUST cover I/O boundaries.
4. **Model validation** — DataAnnotations + FluentValidation (or equivalent) MUST validate every API request and persisted entity.
5. **CI build and test** — CI MUST rebuild from clean, run all tests, and fail on any warning or analyzer diagnostic. Local builds are advisory; CI is enforced.
6. **Runtime telemetry** — OpenTelemetry traces + structured logs + metrics MUST surface exceptions and latency anomalies in production.
7. **Shakedown** — §24 covers integration paths the unit suite cannot.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — A green local `dotnet build` is one signal. It does NOT prove the build is clean on a fresh agent or the tests pass under load.
- **Two is a tie** — If the compiler is clean but a single test fails, the build is NOT shippable. Two disagreeing signals require a third arbiter (a passing CI run on a clean image) before merge.
- **Three is a quorum** — Compiler/analyzers + tests + production telemetry are the three voting layers. Majority MUST agree before shipping; a single dissent freezes the change.

Example: an analyzer warning suppressed locally with `#pragma` is a single human's vote against two automated voters — restore the analyzer rather than override two of three.

---
[Back to Overview](./OVERVIEW.md)
