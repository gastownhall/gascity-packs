# Error Messages and Exit Codes

### Error Message Requirements
- **Specific**: what failed.
- **Contextual**: where it failed.
- **Actionable**: how to fix.
- **stderr-routed**: always `>&2`.

```bash
# Good
printf 'ERROR: Cannot read config file: %s (check permissions)\n' "${CONFIG_FILE}" >&2
```

### die Function
```bash
die() {
    local msg="$1" rc="${2:-1}"
    printf 'ERROR: %s\n' "${msg}" >&2
    printf '  Script: %s\n' "${BASH_SOURCE[1]:-unknown}" >&2
    printf '  Line: %s\n' "${BASH_LINENO[0]:-unknown}" >&2
    printf '  Function: %s\n' "${FUNCNAME[1]:-main}" >&2
    exit "${rc}"
}
```

### Exit Code Conventions
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General / unspecified error |
| 2 | Incorrect usage / invalid arguments |
| 3 | Pre-flight failure (missing dependency, file, permission) |
| 130 | Interrupted by SIGINT (Ctrl+C) |
| 143 | Terminated by SIGTERM |

Forbidden:
- Bare `exit` without code — always specify.
- Exit codes above 125 except for signal-based exits.

---
[Back to Overview](./OVERVIEW.md)
