# Testing and Validation

## Testing Scripts

### Dry-Run Mode
```bash
DRY_RUN="${DRY_RUN:-0}"
run_cmd() {
    if [[ "${DRY_RUN}" == "1" ]]; then
        printf '%b\n' "${FG_C}[DRY-RUN] $*${RST}"
    else
        "$@"
    fi
}
```

### Test Harness Pattern
```bash
test_function() {
    local name="$1" expected="$2"
    shift 2
    local actual
    actual="$("$@" 2>&1)" || true
    if [[ "${actual}" == "${expected}" ]]; then
        printf 'PASS: %s\n' "${name}"
    else
        printf 'FAIL: %s\n  Expected: %s\n  Actual: %s\n' "${name}" "${expected}" "${actual}"
        return 1
    fi
}
```

### Isolated Environment Testing
Automation scripts must be validated on a clean system (fresh VM, container) to verify dependencies are correctly detected and no implicit host-state assumptions exist.

## Validation Utilities

### Script Syntax Validation
```bash
validate_syntax() {
    local script="$1"
    bash -n "${script}" 2>&1
}
```

### ShellCheck Integration
Scripts should pass shellcheck with warning level.
```bash
validate_shellcheck() {
    local script="$1"
    shellcheck -x -S warning "${script}"
}
```

### Common Shellcheck Rules to Address
- **SC2086** — Quote variables to prevent word splitting.
- **SC2046** — Quote command substitutions.
- **SC2164** — Use `cd ... || exit` in case `cd` fails.
- **SC2155** — Declare and assign separately.

### Environment Validation
```bash
require_env() {
    local missing=0 var
    for var in "$@"; do
        [[ -n "${!var:-}" ]] || { printf 'Missing env: %s\n' "${var}" >&2; missing=$((missing + 1)); }
    done
    return "${missing}"
}
```

---
[Back to Overview](./OVERVIEW.md)
