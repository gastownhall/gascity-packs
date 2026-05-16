# Plugin Architecture

### Plugin Application Strategy

Apply plugins through the `plugins {}` block with version resolution via settings or version catalogs.

```kotlin
plugins {
    `java-library`
    alias(libs.plugins.kotlin.jvm)
    alias(libs.plugins.shadow)
}
```

Forbidden — legacy `apply plugin:` syntax defeats plugin resolution, type safety, and configuration avoidance:

```kotlin
// WRONG
apply(plugin = "java-library")
```

Plugin versions resolve once in `settings.gradle.kts pluginManagement` block or via the version catalog `[plugins]` section. Never specify versions in subproject `plugins {}` blocks when centralized in settings.

### Convention Plugin Development

Extract repeated configuration to convention plugins in `buildSrc/` or an included build (`build-logic/`). Convention plugins are precompiled script plugins written as `.gradle.kts` files in `src/main/kotlin/`. Name with a reverse-domain pattern: `com.company.java-conventions`.

```kotlin
// buildSrc/build.gradle.kts
plugins {
    `kotlin-dsl`
}

dependencies {
    implementation(libs.kotlin.gradle.plugin)
}
```

```kotlin
// buildSrc/src/main/kotlin/com.company.java-conventions.gradle.kts
plugins {
    `java-library`
    jacoco
}

java {
    toolchain {
        languageVersion.set(JavaLanguageVersion.of(21))
        vendor.set(JvmVendorSpec.ADOPTIUM)
    }
    withSourcesJar()
    withJavadocJar()
}

tasks.withType<Test>().configureEach {
    useJUnitPlatform()
    maxParallelForks = (Runtime.getRuntime().availableProcessors() / 2).coerceAtLeast(1)
    testLogging {
        events("passed", "skipped", "failed")
    }
}

tasks.withType<JavaCompile>().configureEach {
    options.compilerArgs.addAll(listOf("-Werror", "-Xlint:all"))
}
```

| Approach | Use When |
|:---------|:---------|
| `buildSrc/` | Simplest. Single repo, single team. `kotlin-dsl` plugin, plugin dependencies, scripts in `src/main/kotlin/`. |
| Included `build-logic/` | Larger orgs or shared build logic across repositories. Composite builds. Isolates build logic dependencies from production code dependencies. |

Subprojects apply convention plugins by ID:

```kotlin
plugins {
    id("com.company.java-conventions")
}
```

---
[Back to Overview](./OVERVIEW.md)
