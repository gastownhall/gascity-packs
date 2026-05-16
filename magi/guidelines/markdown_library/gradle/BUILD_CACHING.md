# Build Caching

### Build Cache Configuration

```properties
# gradle.properties
org.gradle.caching=true
```

```kotlin
// settings.gradle.kts
buildCache {
    local {
        directory = File(rootDir, ".gradle/build-cache")
        removeUnusedEntriesAfterDays = 30
    }
    remote<HttpBuildCache> {
        url = uri(providers.gradleProperty("buildCacheUrl").get())
        credentials {
            username = providers.gradleProperty("buildCacheUser").get()
            password = providers.gradleProperty("buildCachePassword").get()
        }
        isPush = providers.environmentVariable("CI").isPresent
    }
}
```

- Local cache stores task outputs on disk for reuse across builds.
- Remote cache (HTTP build cache or Develocity) shares outputs across machines.
- CI pushes to remote cache; developer machines pull only.
- Cache credentials come from environment variables or `gradle.properties` in `GRADLE_USER_HOME`, never committed to the repository.

### Task Cacheability Requirements

Tasks with declared inputs and outputs are cacheable when:

- All inputs are declared with appropriate annotations.
- Outputs are deterministic given the same inputs.
- No host-specific paths leak into outputs.
- Task class implements proper `equals`/`hashCode` or uses the Property API.

Enable `@CacheableTask` annotation on custom tasks. Use `@PathSensitive(PathSensitivity.RELATIVE)` for path inputs to enable cache portability across machines.

### Parallel Execution

```properties
org.gradle.parallel=true
org.gradle.workers.max=8
```

Parallel execution runs independent tasks concurrently. Reduce worker count for memory-constrained environments. Task dependencies serialize execution where required — parallel execution does not break dependency ordering.

---
[Back to Overview](./OVERVIEW.md)
