# Execution Model

### Shebang
```bash
#!/usr/bin/env bash
```
No `/bin/bash` or platform-specific paths. Ever.

### Strict Mode (immediately after header)
```bash
set -Eeuo pipefail
```
- `-e`: exit on unhandled failure
- `-E`: preserve traps in functions/subshells
- `-u`: error on unset variables
- `-o pipefail`: propagate pipeline failures

Strict mode is a safety net — not a substitute for explicit error handling. Known caveats:
- `-e` does NOT fire inside `if`/`while` conditions, the left side of `&&`/`||` chains, or in certain command-substitution contexts. Always pair critical commands with explicit `|| return`/`|| exit`.
- `-u` triggers on empty arrays in bash <4.4. Use `${arr[@]+"${arr[@]}"}` or `${arr[@]:-}` as a workaround.
- `set +e` is permitted **only** inside cleanup functions (where cascading failures must be suppressed) and inside explicitly documented error-handling blocks. Every `set +e` MUST be paired with a re-enabling `set -e` and a comment explaining why.

### Bash Version Guard
When using features that require a specific bash version (associative arrays: 4.0+, nameref: 4.3+, empty-array fix: 4.4+), guard explicitly near the top:
```bash
if ((BASH_VERSINFO[0] < 4)); then
    printf 'ERROR: This script requires bash 4.0+ (found %s)\n' "${BASH_VERSION}" >&2
    exit 1
fi
```

### OS Detection (required for any system interaction)
```bash
OS="$(uname -s)"
readonly OS
[[ "${OS}" == "Darwin" || "${OS}" == "Linux" ]] || { printf '%s\n' "ERROR: Unsupported OS: ${OS}" >&2; exit 1; }
```

### Path Resolution (before any path operations)
```bash
SCRIPT_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
```
Rules:
- Use `${BASH_SOURCE[0]}`, not `$0`
- Use `--` with `dirname` and `cd`
- Use `-P` with `cd` to resolve symlinks
- Must be `readonly`
- All paths derive from `SCRIPT_DIR`
- Never trust `$PWD`; relative paths forbidden

### Execution Context Assumptions
Scripts may be: invoked via symlink, sourced from another file, executed from any working directory, run via cron/ssh/automation. All file references must be absolute or derived from `SCRIPT_DIR`.

---
[Back to Overview](./OVERVIEW.md)
