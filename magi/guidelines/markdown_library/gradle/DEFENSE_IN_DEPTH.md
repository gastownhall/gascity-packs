# Defense in Depth

Multiple, independent layers protect Gradle build configuration from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Version catalogs** — All versions MUST live in `libs.versions.toml`. Inline versions inside build files are forbidden.
2. **Dependency locking** — `gradle.lockfile` MUST be enabled and committed. Floating versions destroy reproducibility.
3. **Convention plugins** — Build logic MUST live in convention plugins under `buildSrc/` or `build-logic/`. Copy-pasted `build.gradle.kts` is a defect, not a style.
4. **Build cache and configuration cache** — Both MUST be enabled and validated; misconfigured tasks that break caching MUST be fixed, not disabled.
5. **Tests and checks** — `gradle check` MUST run unit tests, integration tests, lint (detekt/ktlint/checkstyle), and code coverage on every PR.
6. **CI clean build** — CI MUST run `./gradlew --no-daemon --refresh-dependencies clean check` on every PR.
7. **Wrapper validation** — `gradle/actions/wrapper-validation` MUST run before any Gradle command in CI.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — A successful local Gradle build is one signal; it does NOT prove a fresh agent will get the same result.
- **Two is a tie** — If two consecutive builds on the same machine produce different outputs, reproducibility is broken; freeze releases until a third deterministic build proves the fix.
- **Three is a quorum** — Local build + clean-CI build + lockfile/checksum verification form the triple. All three MUST agree before tagging a release.

Example: a dependency resolved through `mavenLocal()` locally but missing from the declared repositories is exposed only by the CI agent — the CI run is the third witness.

---
[Back to Overview](./OVERVIEW.md)
