# Defense in Depth

Multiple, independent layers protect Java 17 code from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Compiler warnings** — `javac` with all warnings as errors MUST be enabled.
2. **Static analysis** — SpotBugs + ErrorProne + Checkstyle MUST run as part of the build. They find concurrency, null, and API-misuse bugs the compiler does not.
3. **JUnit tests** — JUnit 5 unit tests MUST cover every service. Mockito or Testcontainers MUST exercise integration boundaries.
4. **Bean validation** — `jakarta.validation` constraints MUST validate every controller input and persisted entity.
5. **JaCoCo coverage** — coverage thresholds MUST be enforced in the build (e.g., 80% line, 70% branch). Coverage is not quality but lack of coverage is opacity.
6. **CI clean build** — CI MUST run a full `verify` on a clean agent. Local builds are advisory.
7. **Shakedown** — the §14 startup shakedown MUST run before traffic is admitted.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — `mvn verify` locally is one signal; a clean-checkout CI run is required before the change is real.
- **Two is a tie** — Compiler clean + tests passing but SpotBugs flagging a concurrency bug is two-versus-one; treat it as a freeze, not a green light.
- **Three is a quorum** — Compiler/analyzers + tests + production telemetry (APM/log aggregator) form the three voting layers; a majority MUST agree before declaring the code healthy.

Example: a passing test that asserts a stub return is one vote; if SpotBugs flags missing synchronization on the real code path, the linter and a stress test together outvote the unit test.

---
[Back to Overview](./OVERVIEW.md)
