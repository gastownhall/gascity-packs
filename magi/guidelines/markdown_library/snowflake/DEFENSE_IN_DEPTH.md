# Defense in Depth

Multiple, independent layers protect the Snowflake data warehouse from a single failure. This is **failure-mode defense in depth** (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Warehouse auto-suspend** — Every warehouse MUST auto-suspend; idle warehouses are revenue leaks.
2. **RBAC and least privilege** — Roles MUST follow least-privilege; `ACCOUNTADMIN` MUST never be the owner of objects.
3. **Time Travel and Fail-Safe** — Time Travel retention MUST be set per data sensitivity; Fail-Safe is the second backstop.
4. **Replication or data cloning** — Critical databases MUST replicate cross-region or cross-account.
5. **Query monitoring and resource monitors** — Resource monitors MUST cap credits per warehouse; query history MUST be reviewed for runaways.
6. **Data quality tests** — dbt tests / Great Expectations MUST validate critical tables daily.
7. **Ingestion and pipeline monitoring** — Ingest latency and failure MUST be alerted on; **silent gaps are the most common Snowflake incident**.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority. Apply this rule to data freshness and pipeline health.

- **One is a claim** — A successful query is one signal; it does NOT prove the underlying data is fresh.
- **Two is a tie** — Pipeline "green" + downstream report failing is the freshness dissent; **the report wins**.
- **Three is a quorum** — Pipeline success + data-quality test pass + freshness SLA monitor form the triple. **All three MUST agree before declaring data ready for reporting.**

**Example:** An ingest job that completes successfully but writes 0 rows because the source schema changed — only the data-quality test catches it.

---
[Back to Overview](./OVERVIEW.md)
