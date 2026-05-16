# Defense in Depth

Multiple, independent layers protect automation and self-healing scripts from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Idempotent design** — Every automation MUST converge on re-run; partial failures MUST be safe to resume.
2. **Dry-run mode** — Every mutating automation MUST support dry-run; the operator confirms intent before action.
3. **Input validation** — Inputs MUST be validated against an explicit schema/contract before any side effect runs.
4. **Audit log** — Every run MUST append a timestamped, structured record (who/what/when/result) to a project-local log.
5. **Rollback or snapshot** — Every mutating automation MUST snapshot or stage state so a failed run is reversible.
6. **Health check after action** — Every automation MUST verify post-conditions; trusting the mutating command alone is one signal.
7. **Monitoring and alerting** — Long-running or scheduled automations MUST emit heartbeats; silent failure is the worst failure.
8. **Shakedown** — §21 covers integration paths the unit and dry-run suites cannot.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — A successful exit code is one claim; without verification it is unverified.
- **Two is a tie** — Exit code + verification disagreeing means the automation lied; freeze and investigate rather than trusting the more convenient signal.
- **Three is a quorum** — Exit code + post-condition verification + audit log entry form the triple. Two of three MUST agree for the run to be considered complete; only when all three agree is success unconditional.

Example: a backup job that exits 0 and writes a log line saying "completed" but the post-condition restore-test fails — the restore test is the third voter and overrides the other two.

---
[Back to Overview](./OVERVIEW.md)
