# Style Summary

| Element | Required Style |
|:--------|:---------------|
| **DSL** | Kotlin DSL exclusively; Groovy only for legacy migration |
| **Version Management** | Version catalogs (`libs.versions.toml`); no inline versions in build scripts |
| **Plugin Application** | `plugins {}` block; versions in settings or catalogs; no legacy `apply` syntax |
| **Task Configuration** | Lazy registration (`tasks.register`); never eager (`tasks.create`); lazy references (`tasks.named`) |
| **Dependencies** | `implementation` default; `api` only for public API exposure; explicit scopes for all dependencies |
| **Repositories** | Centralized in settings with `FAIL_ON_PROJECT_REPOS`; HTTPS only; authenticated internal repos |
| **Multi-Project** | Convention plugins in `buildSrc` or included build; type-safe project accessors; platform BOMs for version alignment |
| **Caching** | Build cache enabled; configuration cache enabled; remote cache for CI; local cache for developers |
| **Toolchains** | Declared toolchain version; Gradle provisions JDK; vendor specification for determinism |
| **Testing** | Test suites for separation; JUnit Platform; parallel execution; separate unit/integration/functional/shakedown |
| **Shakedown** | Dedicated `shakedownTest` source set against the packaged artifact; publish gated on `shakedownTest`; classify pass / fail-blocking / fail-nonblocking / inconclusive |
| **Publishing** | `maven-publish` plugin; signed artifacts; POM metadata; environment-based repository selection |
| **CI/CD** | Wrapper validation; build scans; dependency submission; cache-read-only for PRs |
| **Security** | Dependency verification; secrets via environment / user properties; no committed credentials |
| **Properties** | Providers API for deferred resolution; `gradle.properties` for build behavior; `~/.gradle` for secrets |
| **Task Inputs** | All inputs annotated; `@PathSensitive(RELATIVE)` for portability; Property API throughout |
| **Custom Plugins** | TestKit validated; Property API; extensions with conventions; lazy task registration |
| **Debugging** | Build scans for analysis; `--warning-mode=all` for deprecations; `dependencyInsight` for resolution tracing |
| **Defense in Depth** | Catalogs + lockfiles + convention plugins + caches + tests/checks + clean CI build + wrapper validation |
| **Rule of Three** | Local build + clean-CI build + lockfile/checksum verification MUST agree before tagging a release |

---
[Back to Overview](./OVERVIEW.md)
