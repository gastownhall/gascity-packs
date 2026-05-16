# Anti-Patterns (Absolute Blacklist)

### Control Flow
- `A && B || C` multi-command chains (compact one-liner dispatch is the only exception).
- Relying on `set -e` alone.
- `|| true` outside cleanup.
- Bare `exit`.
- `while true` without timeout.
- Infinite retry loops.

### Output
- `echo` in any form.
- Errors to STDOUT.
- Missing `${RST}` after colors.
- Color codes in log files.
- Using `FG_R` for non-error output.

### Filesystem
- `ls` for existence tests.
- Parsing `ls` output.
- Relative paths.
- Trusting `$PWD`.
- Modifying files without backup.

### Variables
- Implicit globals in functions.
- Undeclared variables.
- Mutable "constants".
- Hard-coded values.
- `local var="$(cmd)"` combined declaration+assignment.

### Sourcing
- `source ./file.sh` (use absolute paths).
- `source` without existence check.
- Double-sourcing without guard.

### Shell / Environment
- `#!/bin/bash` shebang (use `/usr/bin/env bash`).
- Failing without attempting dependency installation.
- `expr` for arithmetic.
- Pipe into `while-read` expecting variable side effects.

### Destructive
- `rm -rf` on unvalidated variables.
- Disabling SSL verification in production.
- Mixing tool versions mid-workflow.
- Using macOS system binaries when Homebrew replacements exist.

### Logging / Security
- Logging passwords, tokens, API keys, or PII.
- Scripts requiring manual setup steps (violates self-sufficiency).

---
[Back to Overview](./OVERVIEW.md)
