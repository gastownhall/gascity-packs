# Defense in Depth

Multiple, independent layers protect Maven build configuration from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **maven-enforcer-plugin** — MUST forbid duplicate dependencies, banned dependencies, and require Java/Maven version. Build correctness is layer one.
2. **dependencyManagement BOM** — All versions MUST come from a centralized BOM or `dependencyManagement`. Floating versions break reproducibility.
3. **Checksums and locked versions** — Every dependency MUST have a checksum verified at resolve time; SNAPSHOT use MUST be restricted.
4. **Reproducible builds** — `project.build.outputTimestamp` MUST be set so artifacts are byte-identical across rebuilds.
5. **CI clean build** — CI MUST run `mvn -B -e -V verify` on a clean agent with a fresh local repo (or an isolated mirror).
6. **Dependency vulnerability scan** — OWASP `dependency-check` or equivalent MUST run on every PR; failures MUST block merge.
7. **Shakedown** — The §17 verify-phase shakedown gates every artifact before release.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — `mvn install` on a developer laptop is one signal; the local repo hides missing transitive dependencies.
- **Two is a tie** — If a build passes locally but the dependency-check report flags a CVE, the local pass does NOT outvote the scanner.
- **Three is a quorum** — Local build + clean-CI build + dependency/license scan form the triple. The artifact is releasable only when all three agree.

Example: a dependency that resolves on dev laptops because it is cached but is not in any declared repository will fail in CI — the CI agent is the third voter that exposes the failure.

---
[Back to Overview](./OVERVIEW.md)
