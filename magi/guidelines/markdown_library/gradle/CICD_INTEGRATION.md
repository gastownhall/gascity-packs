# CI/CD Integration

### CI Configuration

```yaml
# .github/workflows/ci.yml
name: CI
on:
  push: { branches: [main] }
  pull_request:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: 21

      - uses: gradle/actions/wrapper-validation@v3

      - uses: gradle/actions/setup-gradle@v3
        with:
          cache-read-only: ${{ github.event_name == 'pull_request' }}
          dependency-graph: generate-and-submit
          build-scan-publish: true
          build-scan-terms-of-use-url: 'https://gradle.com/terms-of-service'
          build-scan-terms-of-use-agree: 'yes'

      - run: ./gradlew check shakedownTest --no-daemon

      - if: github.ref == 'refs/heads/main'
        run: ./gradlew publish
```

- `cache-read-only` for pull requests (no cache push from PRs).
- Validate wrapper integrity before every build.
- Generate build scans for debugging failed builds.
- Submit dependency graph for security scanning.
- Publish artifacts only from `main` or release tags.

### Wrapper Validation

Always validate wrapper JAR integrity in CI before executing the build. A compromised wrapper JAR can execute arbitrary code with build permissions.

```yaml
- uses: gradle/actions/wrapper-validation@v3
```

**Wrapper validation is a security gate, not an optional step.**

### CI Caching Strategy

Cache `~/.gradle/caches` and `~/.gradle/wrapper` between CI runs. Key caches by hash of build files (`*.gradle*`, `gradle-wrapper.properties`, `libs.versions.toml`). Restore from partial matches when exact key misses. The official Gradle action handles caching automatically. For remote build cache, configure CI to push and developers to pull-only.

---
[Back to Overview](./OVERVIEW.md)
