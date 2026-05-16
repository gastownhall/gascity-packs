# Source and Common Script Management

### Source File Resolution
All sourced files must use absolute paths derived from `SCRIPT_DIR`:
```bash
COMMON_DIR="${SCRIPT_DIR}/.common"
readonly COMMON_DIR
source_lib() {
    local lib="${COMMON_DIR}/$1"
    [[ -f "${lib}" ]] || { printf 'ERROR: Missing library: %s\n' "${lib}" >&2; exit 1; }
    source "${lib}"
}
```

### Source Guard Pattern (Mandatory)
All sourceable library files must guard against double-sourcing. Guard variable name follows `_SOURCED_<FILENAME>`:
```bash
# At the very top of the library file, after the header:
[[ -n "${_SOURCED_UTILS_SH:-}" ]] && return 0
readonly _SOURCED_UTILS_SH=1
```

### Common Utilities File Convention
When a project has multiple scripts that share functionality, shared code MUST be extracted into a common utilities file. The conventional path is `.common/utils.sh`.
```bash
# Directory layout:
# project/
# ├── .common/
# │   ├── utils.sh
# │   └── platform.sh
# ├── scripts/
# │   ├── deploy.sh
# │   └── build.sh
```

### Library File Requirements
Every shared library file (`.common/*.sh`) must:
- Have a header block documenting purpose and exported functions/variables.
- Include the source guard.
- Have no side effects on source — define functions and `readonly` variables only.
- Never call `exit` — libraries `return`.

### Existence-Checked Sourcing
```bash
UTILS_PATH="${SCRIPT_DIR}/.common/utils.sh"
readonly UTILS_PATH
[[ -f "${UTILS_PATH}" ]] || { printf 'ERROR: Missing: %s\n' "${UTILS_PATH}" >&2; exit 1; }
source "${UTILS_PATH}"
```

### Environment File Loading
```bash
load_env() {
    local env_file="$1"
    [[ -f "${env_file}" ]] || { printf 'ERROR: Missing env: %s\n' "${env_file}" >&2; return 1; }
    set -a
    source "${env_file}"
    set +a
}
```

### Verification After Sourcing
```bash
verify_sourced() {
    local func
    for func in "$@"; do
        declare -F "${func}" >/dev/null 2>&1 || \
            { printf 'ERROR: Expected function not defined: %s\n' "${func}" >&2; return 1; }
    done
}
source_lib "utils.sh"
verify_sourced log_info log_error cleanup_temp || exit 1
```

---
[Back to Overview](./OVERVIEW.md)
