# Portability Requirements

### Absolute Prohibitions

Scripts within `.utilities/` must **never**:

- Reference filenames, paths, or identifiers specific to any consuming project.
- Hardcode IP addresses, hostnames, or credentials.
- Assume specific directory structures outside `.utilities/`.
- Depend on project-specific environment variables without fallbacks.
- Modify files outside `.utilities/` or designated output directories.

### Environment-Driven Design

```bash
# Correct: Environment-driven
PROJECT_ROOT="$(resolve_project_root)"
PROJECT_NAME="${PROJECT_NAME:-$(basename "${PROJECT_ROOT}")}"

# Incorrect: Hardcoded
PROJECT_ROOT="/home/user/my-application"
PROJECT_NAME="my-application"
```

### Path Resolution

```bash
# Correct: Resolved paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMON_DIR="${SCRIPT_DIR}/../.common"

# Incorrect: Relative assumption
COMMON_DIR="../.common"
```

### Breaking Change Prevention

Before modifying any `.utilities/` file:

1. Verify the change doesn't introduce project-specific values.
2. Ensure backward compatibility with existing invocation patterns.
3. Test across multiple consuming projects if available.
4. Document any new environment variable requirements.

### Backward Compatibility Discipline

- **Modifications must not break existing integrations.**
- New features use **optional parameters with sensible defaults**.
- **Function removal requires deprecation warnings across multiple releases.**

---
[Back to Overview](./OVERVIEW.md)
