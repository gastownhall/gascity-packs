# Defense in Depth

Multiple, independent layers protect SQL/database queries from a single failure. This is **failure-mode defense in depth** (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **EXPLAIN-plan review** — `EXPLAIN (ANALYZE, BUFFERS)` MUST be reviewed for any query touching production-scale tables. Plans are the first defense against unintended sequential scans.
2. **SQLFluff / sqlcheck** — A SQL linter MUST pass on every change; style and ambiguity drift hide bugs.
3. **Schema migrations versioned** — Migrations MUST be versioned (Flyway / Liquibase / Alembic), reversible where possible, and applied in CI against a fresh database.
4. **Transactions and savepoints** — Every multi-statement change MUST run inside a transaction with explicit savepoints for partial rollback.
5. **Read-replica validation** — Heavy analytical queries MUST be exercised against a replica or representative dataset before primary-DB rollout.
6. **Backup and restore drill** — Backups MUST be tested by performing a real restore at a documented cadence. **An unverified backup is no backup.**
7. **Shakedown** — A post-DDL shakedown MUST follow every triggering change.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority. Apply this rule whenever a decision in this domain depends on a check, a copy, a vote, or an actor that fails, drifts, or disagrees.

- **One is a claim** — A query that runs locally on 1000 rows is one signal; it does NOT predict behavior on 100M rows.
- **Two is a tie** — `EXPLAIN` looking sane but actual `ANALYZE` timing being orders-of-magnitude worse than expected is the planner-vs-reality dissent; **the timing wins**.
- **Three is a quorum** — `EXPLAIN` plan + `ANALYZE` timing on representative data + production query telemetry form the triple. **All three MUST agree before deploying a query change.**

**Example:** An index-using plan that still runs slowly in production because of bloat or stale statistics — the production telemetry is the third witness that overrides the planner.

---
[Back to Overview](./OVERVIEW.md)
