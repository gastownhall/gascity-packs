# Defense in Depth

Multiple, independent layers protect bash scripts from a single failure. Every step has a fallback, every assumption is independently verified, every action is reversible.

### Independent Layers of Defense
1. **Strict Mode** — `set -Eeuo pipefail`.
2. **Shellcheck** — must pass with zero warnings.
3. **Dry-Run Mode** — destructive scripts must support `--no-op`.
4. **Idempotent Design** — converging to the same state.
5. **Audit Logging** — timestamped record to a log file.
6. **Retries with Backoff** — handling transient failures.
7. **Post-Condition Verification** — re-reading state after mutation.

### The Rule of Three — Majority Wins
- **One is a claim** — an exit code of 0.
- **Two is a tie** — exit code success but post-condition check fails.
- **Three is a quorum** — exit code + post-condition verification + log entry.

Example: `rm -rf` returning 0 is one signal; re-stating the path is the second; logging the result is the third. Two of three MUST agree.

---
[Back to Overview](./OVERVIEW.md)
