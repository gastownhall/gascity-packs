# Section Ordering (fixed sequence)

1. Header Block
2. Strict Mode & Environment (`set -Eeuo pipefail`, `umask`, OS detection)
3. Script Directory Resolution (`SCRIPT_DIR`)
4. Source Common Utilities (if applicable)
5. Color Definitions (if not sourced from utilities)
6. Constants & Readonly Declarations
7. Logging Setup
8. Privileged Execution Helpers
9. OS/Distribution Detection
10. Dependency Helpers
11. Pre-flight Checks
12. Core Functions
13. Main Logic
14. Cleanup & Exit Hooks

No reordering permitted.

---
[Back to Overview](./OVERVIEW.md)
