# Task Configuration

### Configuration Avoidance

Always use lazy task configuration. `tasks.register` creates tasks that configure only when needed. `tasks.named` references existing tasks lazily. Eager APIs (`tasks.create`, `tasks.getByName`) configure tasks immediately even if they never execute — wastes configuration time and defeats build caching optimizations.

```kotlin
// CORRECT — lazy
val generateBuildInfo = tasks.register<WriteBuildInfo>("generateBuildInfo") {
    outputFile.set(layout.buildDirectory.file("generated/build-info.properties"))
    buildNumber.set(providers.environmentVariable("BUILD_NUMBER").orElse("local"))
}

tasks.named<Jar>("jar") {
    from(generateBuildInfo)
}
```

```kotlin
// FORBIDDEN — eager
tasks.create("generateBuildInfo", WriteBuildInfo::class) { ... }
tasks.getByName("jar") { ... }
```

### Task Inputs and Outputs

Declare all inputs and outputs for cacheability and up-to-date checking.

```kotlin
@CacheableTask
abstract class WriteBuildInfo : DefaultTask() {

    @get:Input
    abstract val buildNumber: Property<String>

    @get:InputFile
    @get:PathSensitive(PathSensitivity.RELATIVE)
    abstract val templateFile: RegularFileProperty

    @get:OutputFile
    abstract val outputFile: RegularFileProperty

    @TaskAction
    fun execute() {
        val template = templateFile.get().asFile.readText()
        outputFile.get().asFile.writeText(
            template.replace("@BUILD_NUMBER@", buildNumber.get())
        )
    }
}
```

| Annotation | Purpose |
|:-----------|:--------|
| `@Input` | Primitive values and serializable objects |
| `@InputFile` | Single file input |
| `@InputDirectory` | Directory input |
| `@InputFiles` | Multiple files / file collections |
| `@OutputFile` | Single file output |
| `@OutputDirectory` | Directory output |
| `@PathSensitive(RELATIVE)` | Portable cache keys across machines |
| `@PathSensitive(NAME_ONLY)` | Only filename matters |
| `@PathSensitive(NONE)` | Path content irrelevant |
| `@CacheableTask` | Task is eligible for build cache |

**Property API and Layout API:**

- Use `Property<T>`, `RegularFileProperty`, `DirectoryProperty`, `ListProperty<T>` for all task inputs and outputs. Properties are lazy, configuration-cache compatible, and support provider chains.
- Use `layout.projectDirectory` and `layout.buildDirectory` for file references. Never use hardcoded paths or `File()` constructors with absolute paths.

### Task Dependencies

Declare dependencies through output-input wiring, not explicit `dependsOn`. When task B uses the output of task A, wire B's input to A's output — Gradle infers the dependency.

```kotlin
// CORRECT — implicit dependency via output wiring
val generateConfig = tasks.register<WriteConfig>("generateConfig") {
    outputFile.set(layout.buildDirectory.file("generated/config.json"))
}

tasks.named<Jar>("jar") {
    from(generateConfig.flatMap { it.outputFile })
}
```

Use `dependsOn` only for lifecycle tasks without produced outputs (`check`, `build`, `assemble`) that aggregate other tasks. Explicit `dependsOn` without output wiring defeats incremental build optimizations.

### Gradle Build Lifecycle

Three distinct phases:

1. **Initialization** — settings script execution, project hierarchy determination.
2. **Configuration** — build script execution, task graph construction.
3. **Execution** — task execution in dependency order.

Configuration cache stores the task graph after configuration — compatible builds skip directly to execution. Avoid executing work during configuration: use providers for deferred value resolution, not immediate computation.

---
[Back to Overview](./OVERVIEW.md)
