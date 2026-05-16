# Defense in Depth

Multiple, independent layers protect `.utilities/` scripts and project automation from a single failure. This is **failure-mode defense in depth** (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Portable shebang and strict mode** — Scripts MUST start with `#!/usr/bin/env bash` and `set -Eeuo pipefail` (or PowerShell strict).
2. **Self-healing dependency resolution** — Scripts MUST detect and install (or instruct on) missing dependencies; **do NOT assume the host**.
3. **Idempotency** — Re-runs MUST converge; nothing in `.utilities/` is permitted to corrupt state on second invocation.
4. **`--dry-run` flag** — Every mutating script MUST accept `--dry-run`.
5. **Project-local logs** — Every run MUST log to a project-local file; **nothing under `/tmp`, `/var/folders`, or temp env vars**.
6. **Post-condition verification** — Every script MUST re-read state after mutation and assert the change took effect.
7. **Documented entry points** — Every script MUST have a usage block printed on `-h`/`--help`. **Tribal knowledge is forbidden.**

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority. Apply this rule to script portability validation.

- **One is a claim** — A passing script run on the author's laptop is one signal; portability is unproven.
- **Two is a tie** — Author's laptop + CI agent passing but a second operator's laptop failing exposes hidden environment assumptions; the third operator decides the script is real.
- **Three is a quorum** — Successful run on **at least three independent environments** (author + CI + a second operator or a clean container) MUST happen before a script is considered production-ready.

**Example:** A script that depends on Homebrew Python at `/opt/homebrew/bin/python3` passes on the author's M-series Mac and fails on Linux CI — the third environment (clean container) reveals the assumption.

---
[Back to Overview](./OVERVIEW.md)
