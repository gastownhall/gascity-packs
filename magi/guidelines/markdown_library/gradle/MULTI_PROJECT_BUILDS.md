# Multi-Project Builds

### Project Structure Patterns

Organize multi-project builds by functional area:

| Directory | Purpose |
|:----------|:--------|
| `apps/` | Deployable applications |
| `libs/` | Shared libraries |
| `platform/` | BOMs and conventions |
| `tools/` | Build-time utilities |

Use directory nesting to group related projects. Project paths in `settings.gradle.kts` reflect the directory structure.

### Inter-Project Dependencies

```kotlin
dependencies {
    implementation(projects.libs.sharedDomain)              // type-safe accessor
    implementation(project(":libs:shared-http"))            // explicit notation
    testImplementation(testFixtures(projects.libs.sharedDomain))
}
```

Inter-project dependencies create task dependencies automatically — changing `lib-core` triggers rebuilds of dependent projects.

### Platform and BOM Projects

Create internal platforms for version alignment using the `java-platform` plugin. Platform projects declare dependency constraints without providing code.

```kotlin
// platform/internal-platform/build.gradle.kts
plugins {
    `java-platform`
}

dependencies {
    constraints {
        api(libs.jackson.databind)
        api(libs.jackson.kotlin)
        api(libs.slf4j.api)
        api(libs.logback.classic)
    }
}
```

Consuming projects import via `platform()` or `enforcedPlatform()`:

```kotlin
dependencies {
    implementation(platform(projects.platform.internalPlatform))
    implementation(libs.jackson.databind)  // version comes from the platform
}
```

### Shared Test Fixtures

Enable the `java-test-fixtures` plugin for projects that provide shared test utilities. Test fixtures have their own source set (`src/testFixtures/`), dependency configurations (`testFixturesApi`, `testFixturesImplementation`), and publication.

```kotlin
plugins {
    `java-library`
    `java-test-fixtures`
}

dependencies {
    testFixturesApi(libs.assertj.core)
    testFixturesImplementation(libs.junit.jupiter)
}
```

Consuming projects:

```kotlin
dependencies {
    testImplementation(testFixtures(projects.libs.sharedDomain))
}
```

---
[Back to Overview](./OVERVIEW.md)
