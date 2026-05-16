# Rollback and Recovery

### Reversibility

Every deployment must be reversible within minutes. The rollback mechanism must be:
- Documented
- Tested
- Executable by any engineer with deployment permissions
- **Not require a new build** — it redeploys the previous artifact

### Artifact Retention

Retain at least the last **5 deployed artifacts** in the registry. Aggressive cleanup that deletes the previous version makes rollback impossible.

### Test Rollback

Practice rollback in staging during routine deployments. **A rollback mechanism that has never been exercised may not work when needed.**

### Forward-Compatible Migrations

Database migrations must be forward-compatible with the previous application version. Two-phase schema changes:
1. First release stops using the column
2. Second release drops it

The rollback sequence: revert application to previous version, then (if necessary) run a compensating migration.

### Automated Rollback Triggers

Trigger automatic rollback on:
- Error rate exceeds threshold (e.g., 5% increase over baseline)
- Latency exceeds SLA
- Health checks fail
- Key business metrics degrade (conversion rate drops, checkout failures spike)

Automated rollback reduces mean time to recovery from minutes to seconds.

---
[Back to Overview](./OVERVIEW.md)
