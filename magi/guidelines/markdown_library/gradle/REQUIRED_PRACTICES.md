# Required Practices

### Always Do

- Use Gradle Wrapper committed to repository with validated JAR.
- Enable configuration cache for all projects.
- Enable build caching with appropriate remote cache for CI.
- Declare all task inputs and outputs for cacheability.
- Use version catalogs for all dependency management.
- Extract repeated configuration to convention plugins.
- Run `--warning-mode=all` periodically to catch deprecations.
- Validate wrapper in CI pipeline before build execution.
- Use toolchains to declare required JDK versions.
- Use type-safe project accessors for inter-project dependencies.
- Enable strict dependency resolution (`failOnVersionConflict()`) for production.
- Lock dependency versions with `./gradlew dependencies --write-locks`.
- Generate build scans for failed CI builds for debugging.
- Review dependency graph changes in pull requests.
- Sign published artifacts with GPG keys.
- Use providers API for deferred value resolution.
- Configure test parallelization based on available resources.
- Separate test suites by type (unit, integration, functional, shakedownTest).
- Run a shakedown after every artifact-affecting change; gate `publish` on `shakedownTest`.

---
[Back to Overview](./OVERVIEW.md)
