# Project Structure

### Standard Directory Layout

Gradle follows Maven conventions for source layout. Deviation requires explicit configuration and creates friction for developers familiar with standard structures.

```text
project-root/
├── settings.gradle.kts
├── build.gradle.kts
├── gradle.properties
├── gradle/
│   ├── libs.versions.toml
│   └── wrapper/
│       ├── gradle-wrapper.jar
│       └── gradle-wrapper.properties
├── buildSrc/                       # OR build-logic/ (included build)
│   ├── build.gradle.kts
│   └── src/main/kotlin/
│       └── com.company.java-conventions.gradle.kts
├── apps/
│   └── service-x/
│       ├── build.gradle.kts
│       └── src/
│           ├── main/{java,kotlin,resources}/
│           ├── test/{java,kotlin,resources}/
│           └── shakedownTest/{java,kotlin,resources}/
└── libs/
    └── shared-domain/
        ├── build.gradle.kts
        └── src/...
```

**Layout Constraints:**

- `gradle/wrapper/` contains `gradle-wrapper.jar` and `gradle-wrapper.properties`. Both files commit to version control. Never download wrapper from untrusted sources.
- The version catalog lives at `gradle/libs.versions.toml`. This is the single source of truth for all dependency versions across the entire build.
- `gradle.properties` at the project root configures build behavior (parallel, caching, JVM args). Secrets never commit to this file.

### Settings Script Organization

The `settings.gradle.kts` file defines the build structure. It executes before any build script and establishes the project hierarchy, plugin management, and dependency resolution rules.

```kotlin
// settings.gradle.kts
pluginManagement {
    repositories {
        gradlePluginPortal()
        mavenCentral()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        mavenCentral()
    }
}

enableFeaturePreview("TYPESAFE_PROJECT_ACCESSORS")

rootProject.name = "my-platform"

include(
    "apps:service-x",
    "libs:shared-domain",
    "libs:shared-http",
)
```

- `repositoriesMode = FAIL_ON_PROJECT_REPOS` centralizes repository declarations in settings. Subprojects cannot declare repositories — guarantees consistent dependency resolution.
- `TYPESAFE_PROJECT_ACCESSORS` enables type-safe inter-project references (`projects.libs.sharedDomain` instead of `project(":libs:shared-domain")`).

### Gradle Properties Hierarchy

Gradle resolves properties from multiple sources, highest to lowest precedence:

1. Command line (`-P` flags).
2. System properties (`-D` flags via `systemProp.` prefix).
3. `gradle.properties` in `GRADLE_USER_HOME` (`~/.gradle/`).
4. `gradle.properties` in project root.
5. Environment variables (via `providers.environmentVariable()`).

Project-level `gradle.properties` is for build behavior (parallel, caching, JVM args), **not** secrets. Sensitive values belong in `~/.gradle/gradle.properties` or CI secret stores.

```properties
# gradle.properties (project root)
org.gradle.parallel=true
org.gradle.caching=true
org.gradle.configuration-cache=true
org.gradle.jvmargs=-Xmx4g -XX:MaxMetaspaceSize=1g -XX:+UseG1GC
org.gradle.workers.max=8
```

---
[Back to Overview](./OVERVIEW.md)
