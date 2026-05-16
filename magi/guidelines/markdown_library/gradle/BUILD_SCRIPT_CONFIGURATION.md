# Build Script Configuration

### Kotlin DSL Requirements

All new projects use Kotlin DSL exclusively. Advantages over Groovy:

- Compile-time type checking catches configuration errors before execution.
- IDE auto-completion surfaces available APIs without documentation lookup.
- Refactoring tools work correctly.
- Explicit typing eliminates stringly-typed configuration errors.
- Consistent syntax with application Kotlin code reduces cognitive load.

### Root Build Script Structure

The root `build.gradle.kts` configures cross-cutting concerns and conventions only. Apply plugins with `apply false` for plugins that subprojects apply selectively. Use `subprojects {}` sparingly for minimal shared configuration (group, version). Extract substantial repeated configuration to convention plugins. The root build script must be readable in under 30 seconds.

```kotlin
// build.gradle.kts (root)
plugins {
    alias(libs.plugins.kotlin.jvm) apply false
    alias(libs.plugins.shadow) apply false
}

allprojects {
    group = "com.company.platform"
    version = providers.gradleProperty("projectVersion").getOrElse("0.0.0-SNAPSHOT")
}
```

### Subproject Build Script Pattern

Individual subproject build scripts declare their specific requirements: convention plugins to apply, dependencies using version catalog accessors, and project-specific task configuration.

```kotlin
// apps/service-x/build.gradle.kts
plugins {
    id("com.company.java-conventions")
    id("com.company.application-conventions")
    alias(libs.plugins.shadow)
}

dependencies {
    implementation(projects.libs.sharedDomain)
    implementation(libs.bundles.jackson)
    implementation(libs.bundles.logging)
    runtimeOnly(libs.postgresql)

    testImplementation(libs.bundles.testing)
    testImplementation(testFixtures(projects.libs.sharedDomain))
}

application {
    mainClass.set("com.company.servicex.Main")
}
```

A well-structured subproject build script is typically under 50 lines. If it exceeds 100 lines, extract to convention plugins or custom tasks.

- Use type-safe version catalog accessors (`libs.guava`, `libs.jackson.databind`) instead of string-based dependency coordinates.
- Use type-safe project accessors (`projects.libs.sharedDomain`) when `TYPESAFE_PROJECT_ACCESSORS` is enabled.

### Build Script Anti-Patterns

Build scripts configure; they do not contain business logic. Never place substantial imperative code in build scripts. If a configuration block exceeds 20 lines, extract it to a plugin. Extract complex logic to:

- **Convention plugins** for reusable configurations.
- **Custom tasks** for isolated, testable units of build work.
- **Build services** for shared resources across task execution.

---
[Back to Overview](./OVERVIEW.md)
