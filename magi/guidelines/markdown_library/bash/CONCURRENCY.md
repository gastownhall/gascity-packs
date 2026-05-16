# Lock Files and Concurrency

### Lock Acquisition
```bash
LOCK_FILE="${SCRIPT_DIR}/.script.lock"
acquire_lock() {
    exec 200>"${LOCK_FILE}"
    flock -n 200 || { printf 'ERROR: Script already running\n' >&2; exit 1; }
    printf '%s\n' "$$" >&200
}
```

### Stale Lock Detection
```bash
check_stale_lock() {
    [[ -f "${LOCK_FILE}" ]] || return 0
    local pid
    pid="$(cat "${LOCK_FILE}" 2>/dev/null)" || return 0
    kill -0 "${pid}" 2>/dev/null && { printf 'ERROR: Process %s holds lock\n' "${pid}" >&2; return 1; }
    printf 'Removing stale lock (PID %s)\n' "${pid}"
    rm -f "${LOCK_FILE}"
}
```

### Background Process Cleanup
```bash
PIDS=()
cleanup_procs() {
    local pid
    for pid in "${PIDS[@]:-}"; do
        kill "${pid}" 2>/dev/null || true
        wait "${pid}" 2>/dev/null || true
    done
}
trap cleanup_procs EXIT
```

---
[Back to Overview](./OVERVIEW.md)
