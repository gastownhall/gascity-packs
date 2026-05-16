# Shakedown — Packaged Artifact Validation

### Definition

A Gradle shakedown is a **dedicated `shakedownTest` source set with its own classpath, its own dependency configurations, and a `shakedownTest` task that consumes the final built artifact and exercises it against real infrastructure**.

Shakedown runs **between build and publish**: the `jar` task must complete before `shakedownTest` begins, and `publishToMavenLocal`, `publish`, and any deployment task must depend on `shakedownTest` passing. **Shakedown validates the composed artifact as it will ship, not the compile outputs.**

### test vs integrationTest vs shakedownTest

| Source Set | Validates | Classpath |
|:-----------|:----------|:----------|
| `test` | Units against stubs or fakes | main compile classpath |
| `integrationTest` | Cross-module wiring with in-memory fakes / lightweight containers | runtime classpath |
| **`shakedownTest`** | **The final packaged artifact (jar / shadowJar / bootJar) against real Testcontainers-provisioned services or a staging endpoint** | **packaged artifact via `configurations.shakedownTestRuntimeClasspath`** |

`shouldRunAfter` chains them: `integrationTest` after `test`, `shakedownTest` after `integrationTest` and after the artifact task.

### Mandatory Triggers

Shakedown is mandatory on:

- First publication of a new artifact.
- Major or minor version bump of any `implementation` or `api` dependency.
- Version catalog additions that affect runtime classpath.
- Gradle version upgrade that touches task graph semantics or configuration cache behavior.
- Convention plugin changes affecting dependency resolution.
- `shadowJar` or `application` plugin configuration changes.
- JVM toolchain version change.
- Introduction of a new publication target or repository.

### Non-Triggers

Shakedown is not required for:

- Patch-level dependency updates within a locked version catalog with no lockfile diff.
- Javadoc or KDoc changes.
- Unit test additions inside the existing `test` source set.
- Build script comment edits.
- Gradle daemon memory tuning.

Changes confined to the `test` source set without touching the production classpath or the artifact-producing tasks are non-triggers.

### Validation Categories

1. **Task graph correctness** — `shakedownTest` transitively depends on the correct artifact task (`jar`, `shadowJar`, or `bootJar`); the task graph wires inputs to outputs rather than relying on implicit `dependsOn`.
2. **Artifact classpath integrity** — the `shakedownTest` classpath consumes the packaged artifact via `configurations.shakedownTestRuntimeClasspath`, **not** `sourceSets.main.output`.
3. **Real infrastructure provisioning** — Testcontainers resources initialize in `@BeforeAll` fixtures and terminate deterministically in `@AfterAll`.
4. **Dependency lockfile consistency** — the locked dependency graph used during shakedown matches the graph that will be published.
5. **Configuration cache compatibility** — `shakedownTest` executes cleanly with `--configuration-cache` enabled.
6. **Publish-gate enforcement** — `publish`, `publishToMavenLocal`, and any custom deploy task declare `shakedownTest` as a dependency so a failing shakedown blocks publication.

### Execution Principles

- **Conservative** — one representative integration scenario per source set.
- **Progressive stress** — smoke that instantiates the artifact's public API → Testcontainers-backed scenario → multi-service scenario.
- **Controlled environment** — Testcontainers images pinned by digest in the version catalog; dedicated Gradle user home for the shakedown build in CI to avoid cache cross-contamination; configuration cache enabled to catch project-capture violations.
- **Observable** — report output to `build/reports/shakedown/`; `--info` logging on `shakedownTest`; build scan publication for CI shakedown runs.
- **Known-good inputs** — fixture data seeded by Testcontainers init scripts and committed to `src/shakedownTest/resources/fixtures/`.
- **No optimization during shakedown** — slow test execution records as a non-blocking finding.

### Execution Pattern

| Step | Action |
|:----:|:-------|
| 1 | Confirm preflight: `./gradlew build` passes; dependency locks are current; wrapper validated |
| 2 | Execute `./gradlew shakedownTest --configuration-cache --no-build-cache` (force real execution, not cached verdicts) |
| 3 | Task graph resolves: `jar` → `shakedownTestClasses` → `shakedownTest` |
| 4 | Testcontainers initialize in `@BeforeAll` |
| 5 | Shakedown tests exercise the public API surface of the packaged artifact |
| 6 | Reports write to `build/reports/shakedown/` |
| 7 | On success, `publish` becomes eligible. On failure, `publish` is blocked by the task graph |
| 8 | Observations record to `build/reports/shakedown/observations.log` |
| 9 | Classify result |

### Result Classification

- **Pass** — `shakedownTest` completes with zero failures, Testcontainers terminate cleanly, reports generate at `build/reports/shakedown/`, publish tasks become eligible.
- **Fail-blocking** — any `shakedownTest` failure, any Testcontainers provisioning failure that is not an environment issue, any classpath divergence between shakedown and publish, configuration cache errors.
- **Fail-nonblocking** — slow test execution above an advisory threshold, verbose warning output from transitive dependencies, cache miss rates higher than baseline on `shakedownTest`.
- **Inconclusive** — Docker unavailable for Testcontainers, staging endpoint unreachable. Fix infrastructure and re-run the specific task.

### Required Artifacts

- `build/reports/shakedown/` containing JUnit XML reports, HTML reports, and a captured stdout/stderr log per test class.
- Build scan URL for the `shakedownTest` task execution.
- Testcontainers startup and shutdown traces.
- Resolved dependency graph from `./gradlew :module:dependencies --configuration shakedownTestRuntimeClasspath`.
- Environment snapshot: Gradle version, JDK toolchain version and vendor, artifact file and SHA-256, Testcontainers image digests, version catalog contents, dependency lockfile.

### Anti-Patterns (Forbidden)

- Wiring `shakedownTest` to `sourceSets.main.output` instead of the packaged artifact — validates the compile classpath, not the publication.
- Using `tasks.create` and `tasks.getByName` in the shakedown registration — defeats configuration avoidance.
- Omitting the `shouldRunAfter` relationship so `shakedownTest` runs before `test` and `integrationTest`.
- Skipping the publish-gate dependency so a failing shakedown does not block publication.
- Running `shakedownTest` with Testcontainers substituted by Mockito mocks.
- Discarding `build/reports/shakedown/` on the next `clean` without archiving.
- Suppressing configuration cache errors with `--no-configuration-cache` instead of fixing the violation.

### Reference Convention

```kotlin
// build.gradle.kts
plugins {
    `java-library`
    `maven-publish`
    alias(libs.plugins.shadow)
}

// Dedicated source set with its own compile and runtime classpaths
val shakedownTest: SourceSet by sourceSets.creating {
    compileClasspath += sourceSets.main.get().output
    runtimeClasspath += output + compileClasspath
}

// Configurations extend test* so version catalog bundles still apply, but remain independent
val shakedownTestImplementation: Configuration by configurations.getting {
    extendsFrom(configurations.testImplementation.get())
}
val shakedownTestRuntimeOnly: Configuration by configurations.getting {
    extendsFrom(configurations.testRuntimeOnly.get())
}

dependencies {
    shakedownTestImplementation(libs.bundles.testing)
    shakedownTestImplementation(libs.testcontainers.junit)
    shakedownTestImplementation(libs.testcontainers.postgresql)
    // Consume the packaged artifact, not the exploded classes directory
    shakedownTestRuntimeOnly(files(tasks.jar.flatMap { it.archiveFile }))
}

// Lazy task registration — configuration avoidance
val shakedownTestTask = tasks.register<Test>("shakedownTest") {
    group = "verification"
    description = "Integration shakedown against the packaged artifact and real infrastructure"

    testClassesDirs = shakedownTest.output.classesDirs
    classpath = shakedownTest.runtimeClasspath

    useJUnitPlatform()

    // Wire the input-output relationship so Gradle infers task dependencies
    inputs.file(tasks.jar.flatMap { it.archiveFile })
        .withPropertyName("packagedArtifact")
        .withPathSensitivity(PathSensitivity.RELATIVE)

    // Reports route to build/reports/shakedown
    reports {
        html.outputLocation.set(layout.buildDirectory.dir("reports/shakedown/html"))
        junitXml.outputLocation.set(layout.buildDirectory.dir("reports/shakedown/xml"))
    }

    // Ensure ordering: unit tests → integration tests → shakedown
    shouldRunAfter(tasks.test)

    // Surface Testcontainers and startup traces at --info level
    testLogging {
        events("passed", "skipped", "failed", "standardError")
        showStandardStreams = true
        showExceptions = true
        showStackTraces = true
    }

    // Fail fast on infrastructure provisioning errors
    failFast = true
}

// Lifecycle wiring: check aggregates shakedownTest; publish is gated on shakedownTest
tasks.named("check") {
    dependsOn(shakedownTestTask)
}

tasks.withType<PublishToMavenRepository>().configureEach {
    dependsOn(shakedownTestTask)
}

tasks.withType<PublishToMavenLocal>().configureEach {
    dependsOn(shakedownTestTask)
}
```

---
[Back to Overview](./OVERVIEW.md)
