# Configuration Cache

### Enabling Configuration Cache

```properties
# gradle.properties
org.gradle.configuration-cache=true
```

Configuration cache stores the serialized task graph after configuration. Subsequent builds skip configuration entirely when build scripts and configuration inputs are unchanged. Eliminates repeated build script evaluation, providing significant speedup for incremental builds.

### Compatibility Requirements

Tasks must avoid capturing non-serializable state during configuration:

- Do not capture `Project` instances in task actions — capture needed values as properties during configuration.
- Use providers for deferred value resolution.
- Build services require `@ServiceReference` annotation.

```bash
./gradlew build --configuration-cache --configuration-cache-problems=warn
```

Forbidden — referencing `Project` in task actions:

```kotlin
// WRONG — captures Project, breaks configuration cache
tasks.register("printName") {
    doLast {
        println(project.name)  // Project captured into action
    }
}

// CORRECT — capture during configuration
tasks.register("printName") {
    val name = project.name
    doLast {
        println(name)
    }
}
```

---
[Back to Overview](./OVERVIEW.md)
