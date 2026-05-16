# Pre-flight and Shakedown

## Pre-flight Checks
Pre-flight checks must verify everything required for successful execution before any mutating operations occur.

### What Pre-flight Must Validate
1. **All required commands exist** (`command -v`)
2. **All required files exist and are readable**
3. **All required directories exist or are creatable**
4. **All required environment variables are set**
5. **Sufficient permissions** for all operations
6. **Network connectivity** if network operations required
7. **Disk space** if significant writes expected
8. **Version compatibility** for critical dependencies

### Pre-flight Function Pattern
Accumulate errors and report all at once:
```bash
preflight() {
    local errors=0
    for cmd in docker git jq curl; do
        command -v "${cmd}" >/dev/null 2>&1 || { printf '%b\n' "${FG_R}ERROR: Missing command: ${cmd}${RST}" >&2; errors=$((errors + 1)); }
    done
    [[ -f "${CONFIG_FILE}" ]] || { printf '%b\n' "${FG_R}ERROR: Missing config: ${CONFIG_FILE}${RST}" >&2; errors=$((errors + 1)); }
    [[ -r "${CONFIG_FILE}" ]] || { printf '%b\n' "${FG_R}ERROR: Cannot read config: ${CONFIG_FILE}${RST}" >&2; errors=$((errors + 1)); }
    [[ -w "${OUTPUT_DIR}" ]] || { printf '%b\n' "${FG_R}ERROR: Cannot write to: ${OUTPUT_DIR}${RST}" >&2; errors=$((errors + 1)); }
    [[ -n "${API_KEY:-}" ]] || { printf '%b\n' "${FG_R}ERROR: API_KEY not set${RST}" >&2; errors=$((errors + 1)); }
    ((errors == 0)) || { printf '%b\n' "${FG_R}Pre-flight failed with ${errors} errors${RST}" >&2; exit 3; }
}
```

### Network Pre-flight
```bash
check_connectivity() {
    local host="$1" timeout="${2:-5}"
    curl -sf --max-time "${timeout}" "https://${host}" >/dev/null 2>&1 || \
        { printf 'ERROR: Cannot reach %s\n' "${host}" >&2; return 1; }
}
```

### Disk Space Pre-flight
```bash
check_disk_space() {
    local path="$1" required_mb="$2" available
    available=$(df -m "${path}" | awk 'NR==2 {print $4}')
    ((available >= required_mb)) || \
        { printf 'ERROR: Insufficient space in %s (%dMB available, %dMB required)\n' "${path}" "${available}" "${required_mb}" >&2; return 1; }
}
```

---

## Shakedown

### Definition
A shakedown is the first controlled end-to-end execution of a bash script against real subsystems after any change that touches integration boundaries. It exercises the actual pipes, redirects, external commands, trap handlers, and lock files the script uses in production. Shakedown validates that the script operates correctly as an integrated whole.

It is not preflight (static inspection) and not a test suite (behavioral verification).

### Shakedown vs Preflight vs Testing
- **Preflight**: prerequisites exist before the script runs.
- **Shakedown**: the script executes the full integrated path correctly under real conditions.
- **Testing**: behavioral correctness, performance, and edge cases.

### Mandatory Shakedown Triggers
Shakedown is required when:
- First execution of a newly written script
- Any change to subprocess invocations, pipelines, or redirects
- Any change to trap handlers, exit codes, or `set -e`/`set -o pipefail` semantics
- Any change to sourced libraries or sourced configuration files
- Any change to lock file, PID file, or temporary file handling
- Any change to file descriptor manipulation (`exec 3<` patterns, here-documents)
- Any dependency upgrade for commands the script invokes (jq, curl, docker, git, etc.)
- OS or shell version upgrade on the target host

### Validation Categories (Six Integration Surfaces)
Shakedown must exercise each surface that bash scripts actually fail on:
1. **Data flow** through pipes, redirects, stdin, and stdout.
2. **Subsystem communication** — every external command connects, authenticates, and returns parseable output.
3. **Resource availability** — file descriptors, lock files, PID files, cleanup traps.
4. **Configuration propagation** — environment variables reach the subshells.
5. **Error handling paths** — failing commands trigger the expected trap, `set -e` behavior.
6. **Side effect correctness** — file writes land in the intended path, idempotency holds.

### Shakedown Function Pattern
```bash
shakedown() {
    local failures=0
    local scratch="${SCRIPT_DIR}/.shakedown"
    mkdir -p "${scratch}" || { printf '%b\n' "${FG_R}SHAKEDOWN: cannot create scratch dir${RST}" >&2; return 1; }
    trap 'rm -rf "${scratch}"' RETURN
    #
    printf '%b\n' "${FG_B}SHAKEDOWN[1/6]${RST} data flow"
    printf 'fixture\n' | process_input > "${scratch}/out.txt" 2> "${scratch}/err.txt" \
        || { printf '%b\n' "${FG_R}FAIL: pipeline dropped input${RST}" >&2; failures=$((failures + 1)); }
    [[ -s "${scratch}/out.txt" ]] \
        || { printf '%b\n' "${FG_R}FAIL: pipeline produced empty output${RST}" >&2; failures=$((failures + 1)); }
    # ... more shakedown logic ...
    if ((failures == 0)); then
        printf '%b\n' "${FG_G}SHAKEDOWN: PASS${RST}"
        return 0
    fi
    printf '%b\n' "${FG_R}SHAKEDOWN: FAIL (${failures} category failures)${RST}" >&2
    return 1
}
```

### Required Artifacts
Every shakedown run produces four artifacts written to the project-local scratch directory:
1. **Execution log** with full, timestamped subprocess output.
2. **Result summary** with pass/fail classification per validation category.
3. **Issue list** with every observed anomaly classified blocking/non-blocking/deferred.
4. **Environment snapshot** recording tool versions and relevant env vars.

---
[Back to Overview](./OVERVIEW.md)
