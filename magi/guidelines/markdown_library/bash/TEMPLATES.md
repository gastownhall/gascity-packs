# Script Templates

## Standalone Script (no shared library)
```bash
#!/usr/bin/env bash
#
# Script Name
# ==============================================================================
# Description of what this script does.
#
# USAGE:
#   ./script.sh [OPTIONS]
# ==============================================================================
set -Eeuo pipefail
SCRIPT_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
OS="$(uname -s)"
readonly OS

# --- Color Definitions ---
readonly RST=$'\033[0m'
readonly FG_R=$'\033[31m' FG_G=$'\033[32m' FG_B=$'\033[34m'

# --- Logging Setup ---
setup_logging() {
    # ... logging logic ...
}

# --- Cleanup ---
cleanup() {
    local rc=$?
    # ... cleanup logic ...
    exit "${rc}"
}
trap cleanup EXIT

# --- Main ---
main() {
    setup_logging
    # ...
}
main "$@"
```

## Script with Shared Library
```bash
#!/usr/bin/env bash
# ... header ...
set -Eeuo pipefail
SCRIPT_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR

# --- Source Common Utilities ---
COMMON_DIR="${SCRIPT_DIR}/../.common"
readonly COMMON_DIR
[[ -f "${COMMON_DIR}/utils.sh" ]] || { printf 'ERROR: Missing: %s/utils.sh\n' "${COMMON_DIR}" >&2; exit 1; }
source "${COMMON_DIR}/utils.sh"

main() {
    setup_logging
    # ...
}
main "$@"
```

## Common Utilities Library (.common/utils.sh)
```bash
#!/usr/bin/env bash
# ... header ...

# --- Source Guard ---
[[ -n "${_SOURCED_UTILS_SH:-}" ]] && return 0
readonly _SOURCED_UTILS_SH=1

# --- Color Definitions ---
readonly RST=$'\033[0m'
readonly FG_R=$'\033[31m' FG_G=$'\033[32m' FG_B=$'\033[34m'

# --- OS Detection ---
OS="$(uname -s)"
readonly OS
```

---
[Back to Overview](./OVERVIEW.md)
