# Architecture Overview

### Layered Module System

| Layer | Path | Stability |
|:------|:-----|:----------|
| **Foundation** | `.common/` | Platform abstraction, utility functions, environment loading, logging infrastructure. Every script depends on this layer. Changes propagate globally. |
| **Domain** | `.backend/`, `.docker/`, `.errors/`, `.frontend/`, `.local_azure/` | Specialized tooling per workflow domain. Each domain operates independently. **Cross-domain dependencies are prohibited.** |
| **Integration** | `.tools/` | Optional connectors to external services (LM Studio). **Experimental** — may change without notice. Production workflows must not depend on this layer. |

### Dependency Graph

Module dependencies flow strictly downward:

```text
┌──────────────────────────────────────────────────────────────────┐
│                        Integration Layer                         │
│                            (.tools/)                             │
├──────────────────────────────────────────────────────────────────┤
│                          Domain Layer                            │
│   .backend/   .docker/   .errors/   .frontend/   .local_azure/   │
├──────────────────────────────────────────────────────────────────┤
│                       Foundation Layer                           │
│                          (.common/)                              │
└──────────────────────────────────────────────────────────────────┘
```

- Domain modules may source foundation modules.
- Integration modules may source both foundation and domain modules.
- Foundation modules may **only** source other foundation modules — and only when explicitly required to prevent circular references.

### Script Initialization Sequence

| Step | Action |
|:----:|:-------|
| 1 | Strict mode activation (`set -Eeuo pipefail`) |
| 2 | Umask configuration (`umask 022`) |
| 3 | Script directory resolution |
| 4 | Common directory path derivation |
| 5 | Required helper validation and sourcing |
| 6 | OS detection and platform-specific setup |
| 7 | Environment loading from project root |
| 8 | Tool-specific initialization |
| 9 | Argument parsing |
| 10 | Main execution |
| 11 | Cleanup trap handling |

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
umask 022
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMON_DIR="${SCRIPT_DIR}/../.common"
[[ -f "${COMMON_DIR}/colors.sh" ]] || { echo "ERROR: Missing colors.sh"; exit 1; }
source "${COMMON_DIR}/colors.sh"
[[ -f "${COMMON_DIR}/utils.sh" ]] || { echo -e "${RED}ERROR:${NC} Missing utils.sh"; exit 1; }
source "${COMMON_DIR}/utils.sh"
```

---
[Back to Overview](./OVERVIEW.md)
