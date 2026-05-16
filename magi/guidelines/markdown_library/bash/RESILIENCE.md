# Idempotency, Self-Healing, and Resilience

## Idempotency Requirement
Every script must be safely re-runnable. Running a script N times must produce the same end state as running it once.

### Idempotent Patterns
- **File creation**: `[[ -f "${target}" ]] || create_file "${target}"`
- **Directory creation**: `mkdir -p "${dir}"`
- **Symlink creation**: `[[ -L "${link}" && "$(readlink "${link}")" == "${target}" ]] || ln -sf "${target}" "${link}"`
- **Package installation**: `command -v "${cmd}" >/dev/null 2>&1 || install_package "${pkg}"`
- **Service state**: `systemctl is-active --quiet "${service}" || systemctl start "${service}"`

## Self-Healing Loop
1. **Detect** — check prerequisites.
2. **Correct** — fix missing/invalid prerequisites.
3. **Verify** — confirm corrections succeeded.
4. **Execute** — perform the primary operation.
5. **Validate** — confirm the operation achieved its objective.
6. **Clean** — remove temporary resources.

### State Persistence for Multi-Phase Operations
Record completed phases to a state file so re-runs skip already-completed work.
```bash
STATE_FILE="${SCRIPT_DIR}/.state"
phase_complete() { grep -qxF "$1" "${STATE_FILE}" 2>/dev/null; }
mark_phase() { printf '%s\n' "$1" >> "${STATE_FILE}"; }
```

## Retry and Resilience

### Retry with Exponential Backoff
Transient failures should be retried with exponential backoff.
```bash
retry_backoff() {
    local max_attempts="${1:-5}" initial_delay="${2:-1}" max_delay="${3:-60}"
    shift 3
    local attempt=1 delay="${initial_delay}"
    while ((attempt <= max_attempts)); do
        "$@" && return 0
        ((attempt == max_attempts)) && return 1
        sleep "${delay}"
        delay=$((delay * 2))
        ((delay > max_delay)) && delay="${max_delay}"
        attempt=$((attempt + 1))
    done
}
```

### Jitter for Distributed Systems
Add random jitter to prevent thundering herd in CI or fleet environments.

### Timeouts for All Waits
Every operation that waits on an external resource MUST have a timeout.
```bash
wait_for_service() {
    local url="$1" max_wait="${2:-60}" start elapsed
    start="$(date +%s)"
    while true; do
        curl -sf "${url}" >/dev/null 2>&1 && return 0
        elapsed=$(( $(date +%s) - start ))
        ((elapsed >= max_wait)) && return 1
        sleep 2
    done
}
```

---
[Back to Overview](./OVERVIEW.md)
