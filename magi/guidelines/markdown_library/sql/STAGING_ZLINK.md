# Temporary Staging and zlink Tables

This section defines strict rules for temporary tables used during migrations, backfills, and data repair operations. In particular, it addresses **zlink tables**: temporary linking/staging tables created to associate records across schemas or to perform controlled data movement.

### Definitions

| Term | Meaning |
|:-----|:--------|
| Temporary table | Engine-scoped table that automatically disappears (SQL Server `#temp`, PostgreSQL `TEMP TABLE`). Preferred when supported. |
| Staging table | Persistent table created temporarily for multi-step workflows where engine-scoped temp tables are not feasible. |
| zlink table | A staging table with a specific purpose: linking old identifiers to new identifiers or bridging relationships during a refactor/migration. |

### Primary Rule: Temporary Data Must Have a Deletion Plan

Any non-engine-scoped staging/zlink table is an operational liability. It must be:

- Created intentionally, not ad-hoc.
- Discoverable (naming convention).
- Access-controlled.
- Auditable.
- Removed promptly and deterministically.

### Naming and Placement

| Prefix | Use |
|:-------|:----|
| `zlink_{feature}_{purpose}` | Linking tables |
| `zstage_{feature}_{purpose}` | Staging tables |

Place in a dedicated schema (`maintenance`, `migration`). **Prohibit creating staging/zlink tables in the primary application schema** unless the schema design explicitly includes them.

### Required Columns for Persistent zlink Tables

- `id` (surrogate key) OR a composite primary key that guarantees uniqueness of the mapping
- `created_at` (timestamp) with a default
- `created_by` (actor or migration identifier) when feasible
- A deterministic mapping pair: `old_id` and `new_id` (or equivalent)
- Optional but recommended:
  - `batch_id` to support resumable and parallel-safe backfills
  - `notes` for exceptional cases, not for general metadata

### Constraints and Indexing

zlink tables must enforce correctness with constraints:

- `PRIMARY KEY` on the natural mapping identity.
- `UNIQUE` on `old_id` if each old record maps to at most one new record.
- `UNIQUE` on `new_id` if reverse uniqueness is required.
- `NOT NULL` on mapping columns unless null has explicit meaning.

Index for the access pattern:

- Index `old_id` for lookups during transformation.
- Index `new_id` for reverse verification and reconciliation.
- **Do not leave zlink tables without indexes** if they will be used for joining or existence checks.

### Cleanup Requirements

Every migration that creates a persistent staging/zlink table must also include a cleanup mechanism that runs after successful completion and remains safe to rerun:

- **Idempotent drop** — always drop with `IF EXISTS` guards where supported.
- **Failure-safe cleanup** — rollback (down) must remove the table if and only if it is safe to do so. If rollback cannot safely drop the table, it must leave a clear, documented recovery path and an explicit later cleanup migration.
- **Time-bounded retention** — define a maximum lifetime for staging/zlink tables (for example, "must be removed within 7 days of deployment"). If tables must persist longer, move the mapping into a permanent, modeled structure and treat it as a first-class table.

### Prefer Engine-Scoped Temp Tables When Possible

Use persistent staging/zlink tables only when:

- The workflow spans multiple deploy steps.
- You require resumability across failures.
- You must coordinate multiple services/jobs.

### Access Control for Temporary Artifacts

- Do not grant application runtime roles access to staging/zlink schemas by default.
- Restrict staging/zlink table access to: migration tooling role, DBA/admin role, specific break-glass operators.
- Audit all reads/writes for staging/zlink tables if they can contain sensitive identifiers.

### Operational Checklist for zlink Workflows

Before running a migration/backfill that uses a zlink table, ensure:

- The mapping uniqueness rules are encoded as constraints.
- There is an index supporting the join predicate used by the backfill.
- The backfill is resumable (batching with deterministic ordering).
- There is an explicit cleanup step and a follow-up verification query.
- The table is placed in a non-application schema with restricted permissions.

---
[Back to Overview](./OVERVIEW.md)
