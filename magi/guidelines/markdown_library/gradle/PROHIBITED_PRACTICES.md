# Prohibited Practices

### Never Do

- Use `tasks.create` or `tasks.getByName` — lazy configuration through `tasks.register` and `tasks.named` is mandatory.
- Declare dependency versions in build scripts — all versions belong in version catalogs.
- Apply plugins with legacy `apply plugin:` syntax — use `plugins {}` block exclusively.
- Use `buildscript {}` blocks except for plugins unavailable in the plugin portal.
- Commit credentials to `gradle.properties` in the repository — secrets belong in CI or user-level properties.
- Use `allprojects {}` or `subprojects {}` for substantial configuration — extract to convention plugins.
- Ignore deprecation warnings — they become errors in future versions.
- Use `compile` or `runtime` configurations — use `api`, `implementation`, `runtimeOnly`.
- Execute substantial work during the configuration phase — defer to task execution.
- Reference `Project` instances in task actions — capture needed values during configuration.
- Use hardcoded paths in task inputs/outputs — use `layout.projectDirectory` and `layout.buildDirectory`.
- Skip wrapper validation in CI — malicious wrapper JARs compromise builds.
- Disable build cache on CI — local-only caching wastes CI compute.
- Use `mavenLocal()` in production builds — introduces non-reproducible resolution.
- Declare repositories in subprojects when using `RepositoriesMode.FAIL_ON_PROJECT_REPOS`.
- Use `afterEvaluate {}` blocks — they defeat configuration avoidance and indicate poor architecture.
- Rely on implicit task dependencies — wire through outputs or declare explicit `dependsOn` for lifecycle tasks only.

---
[Back to Overview](./OVERVIEW.md)
