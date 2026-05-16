# CI / Environment Detection

### CI Environment Detection
Detect CI environments and adapt behavior — disable interactive prompts and color output (unless supported).
```bash
IS_CI="${CI:-0}"
if [[ -n "${GITHUB_ACTIONS:-}" || -n "${GITLAB_CI:-}" || -n "${JENKINS_URL:-}" || -n "${BUILDKITE:-}" ]]; then
    IS_CI=1
fi
readonly IS_CI
```

### Non-Interactive Behavior
Detect whether the script is running in an interactive terminal and adjust accordingly. In non-interactive contexts (CI, cron), disable color codes, suppress progress bars, and never prompt for input:
```bash
if [[ -t 1 ]] && [[ "${IS_CI:-0}" != "1" ]]; then
    USE_COLOR=1
else
    USE_COLOR=0
fi
readonly USE_COLOR
```

---
[Back to Overview](./OVERVIEW.md)
