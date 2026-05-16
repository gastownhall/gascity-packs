# Defense in Depth

Multiple, independent layers protect Power Query / M-language transformations from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Explicit typing** — Every column MUST have an explicit type. Power Query's inferred types drift between runs.
2. **Error row isolation** — Errors MUST be routed to an error queue table, not silently dropped. `Table.SelectRowsWithErrors` MUST be used.
3. **Source system validation** — Source-system row counts and checksums MUST be compared against the loaded fact tables on every refresh.
4. **Query folding verification** — Query folding MUST be verified (View Native Query). Broken folding silently moves work to the gateway and slows refresh.
5. **Incremental refresh policies** — Large fact tables MUST use incremental refresh. Full refresh hides drift.
6. **Dataflow vs dataset separation** — Heavy transformations MUST live in dataflows. Visualization datasets MUST consume cleaned data, not raw.
7. **Monitoring of refresh failures** — Service refresh failures MUST be alerted. Silent failed refreshes lead to stale dashboards.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — A successful refresh is one signal; it does NOT prove the data is correct.
- **Two is a tie** — Refresh success + source row count matching loaded count is two signals; checksum disagreement (third) overrides them.
- **Three is a quorum** — Refresh exit + row count match + column-level checksum/aggregate comparison form the triple. All three MUST agree before declaring a refresh trustworthy.

Example: a refresh that completes with 100% of rows but a column-level sum disagreeing by 0.3% — the checksum is the third voter that catches a silent transformation bug.

---
[Back to Overview](./OVERVIEW.md)
