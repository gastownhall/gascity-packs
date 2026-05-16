# Variables and Constants

### No Magic Strings
All configuration as `readonly` constants:
```bash
readonly DEPLOY_HOST="10.11.12.13"
readonly DEFAULT_TIMEOUT="30"
readonly LOG_DIR="${SCRIPT_DIR}/logs"
```

### Naming Convention
- `UPPER_CASE` for exported/environment variables.
- `UPPER_CASE` with `readonly` for constants.
- `lower_case` for local variables.

### Local Variable Mandate
All function variables declared `local`:
```bash
some_func() {
    local tmp result
    result="$(compute)"
}
```

### Environment Defaulting
```bash
TIMEOUT="${TIMEOUT:-30}"
readonly TIMEOUT
```

### Separate Declaration and Assignment for Command Substitutions
Never combine `local`/`export` declaration with command substitution assignment. The keyword masks the exit code.
```bash
# Correct
local output
output="$(some_command)" || return 1
# Wrong
local output="$(some_command)"
```

---
[Back to Overview](./OVERVIEW.md)
