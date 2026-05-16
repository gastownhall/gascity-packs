# Logging

### Mandatory Logging
ALL bash scripts MUST write a log file during execution. No exceptions. Even simple scripts benefit from a log record proving what ran, when, and whether it succeeded.

Required:
- Every script writes a log file during execution
- Log files live in a structured location (e.g., `${SCRIPT_DIR}/logs/` or a configurable `LOG_DIR`)
- Log filenames include the script name and a timestamp to prevent collisions
- The log file path is printed to console at script start so the user knows where to find it
- Both stdout and stderr captured in the log

### Log Format Requirements
- **Never include ANSI color/escape codes in log files.** Strip them before writing. The recommended regex: `sed -E 's/\x1B\[[0-9;]*[A-Za-z]//g'`. Non-negotiable — log aggregators, grep, awk, and humans expect clean plaintext.
- **Always include timestamps** with millisecond precision for timing analysis
- **Log to a structured location** derived from `SCRIPT_DIR`
- **Logs are append-only** during execution — never overwrite

### FIFO Logger Pattern
```bash
setup_logging() {
    local root="$1" date_tag base
    date_tag="$(date +"%Y%m%d_%H%M%S")"
    base="$(basename -- "${root}")"
    LOG_DIR="${root}/logs"
    LOG_FILE="${LOG_DIR}/${base}-${date_tag}.log"
    LOG_FIFO="${LOG_DIR}/.logfifo.$$"
    mkdir -p "${LOG_DIR}"
    rm -f "${LOG_FIFO}" || true
    mkfifo "${LOG_FIFO}"
    (while IFS= read -r line; do
        printf '%s %s\n' "$(date +"%Y-%m-%d %H:%M:%S.%3N")" "${line}"
    done < "${LOG_FIFO}" | sed -E 's/\x1B\[[0-9;]*[A-Za-z]//g' > "${LOG_FILE}") &
    LOG_PID="$!"
    exec > >(tee "${LOG_FIFO}") 2>&1
    printf '%b\n' "${FG_C}Log file: ${LOG_FILE}${RST}"
}
```

### Timing Logs for Complex Operations
```bash
log_timed() {
    local label="$1" start end elapsed
    shift
    start="$(date +%s%3N)"
    "$@"
    local rc=$?
    end="$(date +%s%3N)"
    elapsed=$((end - start))
    printf '[TIMING] %s: %d.%03ds (exit: %d)\n' "${label}" $((elapsed/1000)) $((elapsed%1000)) "${rc}"
    return "${rc}"
}
```

### Log Retention
For long-lived or scheduled scripts, prune older logs to prevent unbounded disk usage:
```bash
prune_old_logs() {
    local log_dir="$1" retention_days="${2:-30}"
    [[ -d "${log_dir}" ]] || return 0
    find "${log_dir}" -name '*.log' -type f -mtime +"${retention_days}" -delete 2>/dev/null || true
}
```

### Never Log Sensitive Data
Log files must NEVER contain passwords, API keys, tokens, private keys, credit card numbers, SSNs, PII, connection strings with embedded credentials, or session identifiers. Sanitize or redact before logging. When in doubt, do not log the value.

### Logger Cleanup
```bash
cleanup_logging() {
    [[ -n "${LOG_PID:-}" ]] && kill "${LOG_PID}" 2>/dev/null || true
    [[ -n "${LOG_FIFO:-}" ]] && rm -f "${LOG_FIFO}" || true
}
trap cleanup_logging EXIT
```

---
[Back to Overview](./OVERVIEW.md)
