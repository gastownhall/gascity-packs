# Style Summary

| Element | Required Style |
|:--------|:---------------|
| Query Naming | `lowercase_with_underscores`; prefixed by purpose (`prm_`, `fn_`, `stg_`, `tfm_`, `dim_`, `fact_`) |
| Step Naming | PascalCase; descriptive action names; no default names |
| Type Declaration | Explicit types on all columns at ingestion; explicit function signatures |
| Query Organization | Folders by tier: Parameters, Functions, Staging, Transform, Output |
| Loading | Only output queries enabled for load; all others disabled |
| Query Folding | Verify folding on all source-connected steps; restructure to preserve folding |
| Error Handling | try-otherwise patterns for risky operations; custom error records with context; row-level error tracking |
| Parameters | Prefixed with `prm_`; used for all environment-specific values; centralized parameter tables for many parameters |
| Functions | Prefixed with `fn_`; documented with metadata; typed parameters and returns |
| Privacy Levels | Set explicitly on all data sources; no ambiguous levels |
| References | Prefer query references over duplicates; single source of truth |
| Buffering | Use `Table.Buffer` only when repeated access is confirmed necessary |
| Filtering | Apply as early as possible in query chain; maximize source pushdown |
| Column Selection | Select only required columns immediately after source connection |
| Currency Values | `Decimal.Type` exclusively; never `type number` for monetary data |
| Date/Time | Explicit `date` vs `datetime` vs `datetimezone` based on semantic need |
| Incremental Refresh | `RangeStart`/`RangeEnd` parameters mandatory; filter via `[ModifiedDate] >= RangeStart and < RangeEnd` |
| Dataflows | Staging → Transformation → Dataset refresh order; linked + computed entity separation |
| Documentation | Metadata on functions; comments in complex logic; README for query groups |
| Version Control | PBIP format; individual `.m` files; Git workflow |
| Testing | Schema validation; row count checks; function unit tests; regression hashes |
| Deployment | Development → Staging → Production with validation at each stage |
| Shakedown | Real source refresh + sample dataset + Diagnose trace + folding preservation; classify pass / fail-blocking / fail-nonblocking / inconclusive |
| Defense in Depth | Explicit typing + error row isolation + source-system validation + folding verification + incremental refresh + dataflow/dataset separation + refresh monitoring |
| Rule of Three | Refresh exit + row count match + column-level checksum MUST agree before declaring refresh trustworthy |

---
[Back to Overview](./OVERVIEW.md)
