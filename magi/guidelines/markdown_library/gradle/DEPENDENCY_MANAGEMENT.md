# Dependency Management

### Version Catalog Configuration

Centralize all dependency versions in `gradle/libs.versions.toml`. The catalog defines versions, libraries, bundles, and plugins. Build scripts reference catalog entries via type-safe accessors generated at configuration time. **No dependency version appears in build scripts** — all versions resolve through the catalog.

```toml
# gradle/libs.versions.toml
[versions]
kotlin = "1.9.25"
jackson = "2.17.2"
junit = "5.11.0"
testcontainers = "1.20.4"
shadow = "8.1.1"

[libraries]
jackson-databind = { module = "com.fasterxml.jackson.core:jackson-databind", version.ref = "jackson" }
jackson-kotlin = { module = "com.fasterxml.jackson.module:jackson-module-kotlin", version.ref = "jackson" }
jackson-jsr310 = { module = "com.fasterxml.jackson.datatype:jackson-datatype-jsr310", version.ref = "jackson" }

junit-jupiter = { module = "org.junit.jupiter:junit-jupiter", version.ref = "junit" }
junit-platform-launcher = { module = "org.junit.platform:junit-platform-launcher", version = "1.11.0" }
assertj-core = { module = "org.assertj:assertj-core", version = "3.26.3" }

testcontainers-junit = { module = "org.testcontainers:junit-jupiter", version.ref = "testcontainers" }
testcontainers-postgresql = { module = "org.testcontainers:postgresql", version.ref = "testcontainers" }

postgresql = { module = "org.postgresql:postgresql", version = "42.7.4" }
slf4j-api = { module = "org.slf4j:slf4j-api", version = "2.0.16" }
logback-classic = { module = "ch.qos.logback:logback-classic", version = "1.5.8" }

[bundles]
jackson = ["jackson-databind", "jackson-kotlin", "jackson-jsr310"]
logging = ["slf4j-api", "logback-classic"]
testing = ["junit-jupiter", "junit-platform-launcher", "assertj-core"]

[plugins]
kotlin-jvm = { id = "org.jetbrains.kotlin.jvm", version.ref = "kotlin" }
shadow = { id = "com.github.johnrengelman.shadow", version.ref = "shadow" }
```

### Configuration Scopes

| Configuration | Use When |
|:--------------|:---------|
| `implementation` | Default for internal dependencies. Not visible to consumers. |
| `api` | Only when a dependency's types appear in public API signatures (method parameters, return types, public fields, extended classes, implemented interfaces). Excessive `api` forces unnecessary recompilation in dependent modules. |
| `compileOnly` | Compile-time-only dependencies provided at runtime by a container (e.g., servlet API). |
| `runtimeOnly` | Runtime behavior without compile-time dependency (JDBC drivers, logging implementations). |
| `testImplementation` | Test-scope dependencies. |
| `testRuntimeOnly` | Test-runtime-only (e.g., `junit-platform-launcher`). |

Default to `implementation`. Use `api` only when dependency types appear in public API signatures.

### Dependency Locking

Enable dependency locking for reproducible builds.

```kotlin
// build.gradle.kts (or convention plugin)
dependencyLocking {
    lockAllConfigurations()
    lockMode.set(LockMode.STRICT)
}
```

```bash
./gradlew dependencies --write-locks
```

- Commit `gradle.lockfile` per subproject.
- CI validates lock files match resolved dependencies.
- Use `STRICT` lock mode in production to fail builds when lock files are outdated.
- Selective locking applies to production configurations (compile, runtime) while allowing test dependency flexibility.

### Dependency Constraints and BOMs

Enforce version alignment through constraints. Constraints specify minimum or exact versions without adding dependencies. Use `platform()` to import BOMs that provide version recommendations for library families.

```kotlin
dependencies {
    implementation(platform(libs.spring.boot.bom))
    implementation(platform(libs.aws.sdk.bom))

    constraints {
        implementation("com.fasterxml.jackson.core:jackson-databind") {
            version { strictly("2.17.2") }
            because("CVE-2023-XXXX requires >=2.17.2")
        }
    }
}
```

Use `enforcedPlatform()` for hard version pinning across a family.

### Dependency Conflict Resolution

Gradle resolves conflicts by selecting the highest version by default.

```kotlin
configurations.all {
    resolutionStrategy {
        failOnVersionConflict()
        force(libs.jackson.databind.get().toString())
    }
}
```

Visualize the resolved dependency graph:

```bash
./gradlew dependencies --configuration runtimeClasspath
./gradlew dependencyInsight --dependency jackson-databind --configuration runtimeClasspath
```

Understand the resolution before forcing versions.

---
[Back to Overview](./OVERVIEW.md)
