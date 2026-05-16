# Privileged Execution

```bash
can_run_privileged() { [[ $EUID -eq 0 ]] || command -v sudo >/dev/null 2>&1; }
run_privileged() { [[ $EUID -eq 0 ]] && "$@" || sudo "$@"; }
```

Always verify capability before use:
```bash
can_run_privileged || { printf 'ERROR: Requires root or sudo\n' >&2; exit 1; }
```

After authentication, sudo is used ONLY for operations that actually require it; everything else runs unprivileged. Use a dedicated helper to acquire/refresh sudo and a separate helper to run privileged commands; do not sprinkle raw `sudo` calls throughout.

---
[Back to Overview](./OVERVIEW.md)
