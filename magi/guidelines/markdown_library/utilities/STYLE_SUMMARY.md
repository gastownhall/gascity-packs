# Style Summary

| Element | Required Pattern |
|:--------|:-----------------|
| Shebang | `#!/usr/bin/env bash` |
| Strict Mode | `set -Eeuo pipefail` immediately after shebang |
| Umask | `umask 022` after strict mode |
| Path Resolution | `SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"` |
| Common Dir | Derived from `SCRIPT_DIR` with validation |
| Module Sourcing | Check existence then source; `colors.sh` first, then `utils.sh` |
| OS Detection | `uname -s` with case statement for Darwin/Linux |
| Variables | `local` for function scope; `readonly` for constants |
| Error Handling | Use `die` function; never bare `exit 1` |
| Color Usage | Direct echo with `${COLOR}text${NC}` pattern |
| Logging | Via `log_helper.sh` functions to centralized directory |
| Environment | Load via `env_loader.sh`; never hardcode values |
| Dependencies | Auto-install missing tools; provide fallback methods |
| Arguments | Parse with `while [[ $# -gt 0 ]]` case statement |
| Cleanup | `trap cleanup EXIT` for temporary resources |
| Functions | snake_case names; single responsibility; documented |
| Output | Clear status messages with color-coded severity |
| Project Values | Always from environment; never in `.utilities/` |
| Symlinks | Resolve with `BASH_SOURCE` + `readlink -f` for symlinked installations |
| Shakedown | `--shakedown` mode or companion `shakedown.sh`; six categories; four artifacts; pass / fail-blocking / fail-nonblocking / inconclusive |
| Defense in Depth | Strict mode + self-healing deps + idempotency + dry-run + project-local logs + post-condition verification + documented entry points |
| Rule of Three | Author + CI + third independent environment MUST all pass before production-ready |

---

The `.utilities` suite provides a battle-tested foundation for development automation across language ecosystems. Adherence to these guidelines ensures the suite remains portable, maintainable, and useful across the organization's diverse project portfolio. Extensions and modifications must preserve the core invariants: **absolute portability, self-healing dependencies, environment-driven configuration**.

**Apply these guidelines universally to all `.utilities` suite development and usage.**

---
[Back to Overview](./OVERVIEW.md)
