# Cleanup and Traps

### Cleanup Function Requirements
- Idempotent (safe to call multiple times).
- Tolerant of partial initialization.
- Never fails fatally.
- Preserves original exit code.

`set +e` is explicitly permitted inside cleanup to prevent cascading failures.
```bash
cleanup() {
    local rc=$?
    set +e  # Prevent cleanup failures from cascading
    [[ -n "${TMP_DIR:-}" ]] && rm -rf "${TMP_DIR}"
    [[ -n "${LOCK_FILE:-}" ]] && rm -f "${LOCK_FILE}"
    [[ -n "${LOG_FIFO:-}" ]] && rm -f "${LOG_FIFO}"
    [[ -n "${LOG_PID:-}" ]] && kill "${LOG_PID}" 2>/dev/null
    exit "${rc}"
}
trap cleanup EXIT
```

### ERR Trap for Diagnostics
```bash
on_error() {
    local rc=$? line="${BASH_LINENO[0]}" cmd="${BASH_COMMAND}"
    printf 'ERROR: Command failed (rc=%d) at line %d: %s\n' "${rc}" "${line}" "${cmd}" >&2
}
trap on_error ERR
```

### Signal Handling
```bash
trap 'printf "\nInterrupted\n" >&2; exit 130' INT
trap 'printf "Terminated\n" >&2; exit 143' TERM
```

### Trap Stacking
Multiple separate EXIT traps will silently overwrite each other. Consolidate into a single `cleanup()` function.

---
[Back to Overview](./OVERVIEW.md)
