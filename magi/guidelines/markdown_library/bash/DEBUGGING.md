# Debugging and Tracing

### Debug Mode Activation
```bash
DEBUG="${DEBUG:-0}"
readonly DEBUG
[[ "${DEBUG}" == "1" ]] && set -x
```

### Trace-Specific Execution
For isolating failures without modifying script:
```bash
bash -x ./script.sh          # Full trace
bash -v ./script.sh          # Print lines before execution
bash -xv ./script.sh         # Combined
BASH_XTRACEFD=3 bash -x ./script.sh 3>trace.log  # Trace to separate file
```

### Function-Level Tracing
```bash
trace_func() {
    local func="$1"
    shift
    printf '[TRACE] Entering %s with args: %s\n' "${func}" "$*" >&2
    local start rc
    start="$(date +%s%3N)"
    "$func" "$@"
    rc=$?
    printf '[TRACE] Exiting %s after %dms (rc=%d)\n' "${func}" $(( $(date +%s%3N) - start )) "${rc}" >&2
    return "${rc}"
}
```

### PS4 Customization for Detailed Traces
```bash
export PS4='+[${BASH_SOURCE[0]##*/}:${LINENO}] ${FUNCNAME[0]:+${FUNCNAME[0]}(): }'
```

### Conditional Trace Blocks
```bash
debug_dump() {
    [[ "${DEBUG:-0}" == "1" ]] || return 0
    printf '[DEBUG] %s\n' "$@" >&2
}
```

---
[Back to Overview](./OVERVIEW.md)
