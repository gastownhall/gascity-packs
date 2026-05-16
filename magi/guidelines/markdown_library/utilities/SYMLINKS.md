# Symlink Management

### Symlink Resolution

When utilities may be installed via symlinks, scripts must resolve their actual location:

```bash
# Resolve actual script location even through symlinks
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || echo "${BASH_SOURCE[0]}")"
```

- Use `normalize_path_no_deref` for paths that should NOT follow symlinks.
- Always resolve script directory using `BASH_SOURCE`, **never `$0`**.

### Symlink-Aware Sourcing

```bash
# Follow symlinks to find real utilities directory
if [[ -L "${SCRIPT_DIR}" ]]; then
    UTILITIES_ROOT="$(cd "$(dirname "$(readlink -f "${SCRIPT_DIR}")")" && pwd)"
else
    UTILITIES_ROOT="${SCRIPT_DIR}/.."
fi
COMMON_DIR="${UTILITIES_ROOT}/.common"
```

This pattern handles utilities installed as symlinks from a central location while preserving the ability to source modules relative to the real path.

---
[Back to Overview](./OVERVIEW.md)
