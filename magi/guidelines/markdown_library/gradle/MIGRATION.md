# Migration

### Upgrading Gradle Versions

Systematic upgrade process:

1. Review release notes for breaking changes.
2. Run `./gradlew help --scan` on current version for baseline.
3. Update wrapper: `./gradlew wrapper --gradle-version=X.Y`.
4. Run build with `--warning-mode=all` to surface deprecations.
5. Fix deprecations before they become errors.
6. Validate build scan metrics match or improve.

Never skip minor versions in the upgrade path.

### Groovy to Kotlin DSL Migration

Migrate file-by-file:

1. Rename `build.gradle` → `build.gradle.kts`.
2. Add explicit types where needed.
3. Convert Groovy closures to Kotlin lambdas.
4. Replace `=` assignment with `.set()` for properties.
5. Fix string interpolation.

Common conversions:

| Groovy | Kotlin DSL |
|:-------|:-----------|
| `apply plugin: 'java'` | `plugins { java }` |
| `sourceCompatibility = 17` | `java { toolchain { languageVersion.set(JavaLanguageVersion.of(17)) } }` |
| `compile 'group:artifact:version'` | `implementation("group:artifact:version")` |
| `tasks.create('foo')` | `tasks.register("foo")` |
| `tasks.getByName('test')` | `tasks.named("test")` |

---
[Back to Overview](./OVERVIEW.md)
