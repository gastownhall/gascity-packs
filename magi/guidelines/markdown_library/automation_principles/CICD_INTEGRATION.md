# CI/CD Integration

Continuous integration and deployment systems are primary consumers of automation. Self-healing automation integrates smoothly with CI/CD platforms.

### Pipeline Compatibility

- **Exit codes** — Return appropriate exit codes. CI systems use them to determine success/failure.
- **Output formats** — Support machine-parseable output for CI systems. JSON, TAP, or JUnit XML for test results.
- **Timeout handling** — Complete within CI timeout limits. Provide progress output to prevent idle timeouts.
- **Resource cleanup** — Release resources immediately after use. CI runners have limited resources shared across jobs.

### Artifact Management

- **Artifact generation** — Place artifacts in designated directories. Use consistent naming conventions.
- **Artifact caching** — Support CI cache mechanisms for dependencies. Version cache keys appropriately.
- **Artifact retention** — Do not assume artifacts persist between runs. Download dependencies fresh on cache miss.

### Standard Environment Variables

| Variable | Indicates |
|:---------|:----------|
| `CI=true` | CI environment (generic) |
| `GITHUB_ACTIONS` | GitHub Actions |
| `GITLAB_CI` | GitLab CI |
| `JENKINS_URL` | Jenkins |
| `BUILDKITE` | Buildkite |

Use these variables to adapt automation behavior for CI contexts.

### Parallel Execution

CI systems parallelize builds. Automation must handle parallel execution:
- Use unique identifiers for resources (include job ID, runner ID)
- Avoid shared state that creates race conditions
- Support sharded test execution
- Handle port conflicts when multiple instances run on same host

---
[Back to Overview](./OVERVIEW.md)
