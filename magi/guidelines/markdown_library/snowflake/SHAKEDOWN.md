# Shakedown — Post-DDL Integration Validation

### Definition

A Snowflake shakedown is a **mandatory post-DDL integration-validation pass against the real Snowflake account** after any warehouse, database, schema, role, view, stream, task, or pipe change. The shakedown is a **known-good end-to-end execution against the live account** that validates warehouse resume behavior, role resolution, view compilation, stream capture, task firing, Snowpipe ingest, masking and row-access policy enforcement, and micro-partition pruning using a small canary dataset.

| Phase | Question |
|:------|:---------|
| Preflight | Is the account reachable, is key-pair auth working, did `schemachange` or `terraform apply` complete cleanly? |
| **Shakedown** | **Does the freshly applied DDL actually behave correctly against the live account?** |
| Testing | Is behavioral correctness, cost behavior, and scale exercised? |

### Mandatory Triggers

- Warehouse create, resize, auto-suspend change, or scaling policy change.
- Database, schema, table, view, or secure view DDL.
- Role creation, grant, revoke, or role hierarchy change.
- Stream create or recreate, or base-table recreate that invalidates a stream.
- Task create, alter schedule, alter warehouse, or dependency graph change.
- Snowpipe create, stage create, file format change, or storage integration change.
- Masking policy, row access policy, or tag-based policy attach or detach.
- `RESOURCE_MONITOR` create or threshold change.
- `schemachange` or Terraform apply against any environment.

### Non-Triggers

- Routine query execution against an unchanged schema.
- Query tag additions that do not change DDL.
- Result-cache-only query tuning.
- Cost dashboard updates that do not touch the account.

### Validation Categories

Each category is exercised against a dedicated `SHAKEDOWN_DB` (or canary schema) using the application service role.

1. **Warehouse resume** — the target warehouse resumes from `SUSPENDED` within the declared budget when a canary query is issued; `SYSTEM$WAREHOUSE_LOAD_HISTORY` is captured.
2. **Role grant resolution** — the application service role is granted `USAGE` and `SELECT` on every object the application reads; a deliberate query against a forbidden object returns the expected `Insufficient privileges` error.
3. **View and secure-view compilation** — every view and secure view is queried once with `SELECT * FROM ... LIMIT 0` to validate compilation against the new base tables; secure views are additionally queried under a non-privileged role to confirm row filtering.
4. **Stored procedure and UDF execution** — every SQL, Python, Java, or Scala stored procedure and UDF referenced by the application executes against a canary input and returns the expected value.
5. **Stream capture** — a canary INSERT/UPDATE/DELETE against the source table produces a row in the stream within the declared latency window; the stream offset advances after consumption.
6. **Task firing** — the scheduled task is manually executed via `EXECUTE TASK` for the shakedown and also observed to fire on schedule; `TASK_HISTORY` shows `SUCCEEDED`.
7. **Snowpipe ingest** — a canary file dropped into the configured stage is ingested and visible in the target table within the declared latency window; `PIPE_USAGE_HISTORY` and `COPY_HISTORY` confirm the ingest.
8. **Masking policy enforcement** — the application service role reads a masked column and observes the mask; a privileged role reads the same column and observes the unmasked value.
9. **Row access policy enforcement** — a restricted role queries the protected table and observes only the allowed rows; a privileged role observes the full set.
10. **Partition pruning effectiveness** — `EXPLAIN` output for a canary query against the clustered table confirms `partitionsScanned` is significantly less than `partitionsTotal`; **a full table scan on a clustered table is a blocking failure**.
11. **Resource monitor behavior** — `RESOURCE_MONITORS` do not trigger `SUSPEND` under the canary load; a deliberate test of the monitor threshold in a sandbox confirms the suspend action works as configured.

### Execution Principles

- **Conservative execution** — a single canary row per stream, a single canary file per pipe, a single canary task run, **never production data**.
- **Progressive stress** — start with warehouse resume and a trivial `SELECT`, add the view query, add the stream, add the task, add the pipe; stop at the first failure and diagnose.
- **Controlled environment** — a `SHAKEDOWN_DB` (or zero-copy clone of the target database) that mirrors production roles, policies, and clustering configuration.
- **Observable execution** — `QUERY_HISTORY`, `TASK_HISTORY`, `PIPE_USAGE_HISTORY`, `COPY_HISTORY`, `ACCESS_HISTORY`, and `EXPLAIN` output captured for every canary operation.
- **Known-good inputs** — a fixed canary dataset and a fixed canary file in the stage with declared expected post-ingest row counts.
- **No optimization during shakedown** — pruning regressions, clustering depth increases, or warehouse undersize observations are logged as non-blocking findings.

### Execution Order

1. Confirm preflight passes — account URL resolves, key-pair auth or OAuth token valid, schemachange or Terraform reports clean apply.
2. Initialize the canary scope — `SHAKEDOWN_DB` or canary schema cleared of prior canary rows, canary file staged, lease task suspended.
3. Execute the simplest end-to-end path — resume the warehouse, run a trivial `SELECT`, confirm the warehouse state transition.
4. Verify role resolution and view compilation for every application-referenced object.
5. Verify stream capture: `INSERT` a canary row, `SELECT` from the stream, confirm the captured row, consume it, confirm offset advance.
6. Verify task firing: `EXECUTE TASK` the canary task, then wait for one natural schedule firing, confirm both succeed in `TASK_HISTORY`.
7. Verify Snowpipe ingest: `PUT` the canary file, wait for auto-ingest, confirm the row lands in the target table within the latency budget.
8. Verify masking and row access policies under both the restricted role and a privileged role.
9. Capture `EXPLAIN` output for a canary partitioned query and assert pruning effectiveness.
10. Check for orphans — canary rows removed, canary files removed from the stage, lease task resumed or suspended as intended.
11. Classify the result per validation category.

### Result Classification

| Outcome | Trigger |
|:--------|:--------|
| `pass` | Every category completes within its latency budget and returns the expected payload and policy behavior |
| `fail-blocking` | A view fails to compile; a stream misses the canary mutation; a task errors; Snowpipe fails to ingest; a masking or row-access policy leaks; or `EXPLAIN` shows a full scan against a clustered table |
| `fail-nonblocking` | Pruning effectiveness regression; warehouse resume latency creep; micro-partition clustering depth increase that does not alter correctness — logged for a subsequent tuning change |
| `inconclusive` | Cloud services latency, transient network issue, or `RESOURCE_MONITOR` suspension prevented a category from completing — re-run the specific category before declaring shakedown failed |

### Required Artifacts

| Artifact | Contents |
|:---------|:---------|
| Execution log | `QUERY_HISTORY` export filtered to the shakedown query tag, with bytes scanned, partitions scanned, and credits used per canary operation |
| Result summary | Pass/fail classification per validation category |
| Issue list | Every non-blocking anomaly with the originating DDL change and the `SNOWFLAKE.ACCOUNT_USAGE` reference |
| Environment snapshot | Account edition, region, warehouse topology, role hierarchy, active policies, `schemachange` head, Terraform state version at the time of shakedown |

### Anti-Patterns

- Skipping shakedown after a "small" view alter because "the base table did not change".
- Running shakedown against a zero-copy clone that was made **before** the DDL applied.
- Validating a task by inspecting the DDL instead of calling `EXECUTE TASK`.
- Validating Snowpipe by reading the pipe definition instead of `PUT`-ting a canary file.
- Resizing a warehouse or adjusting auto-suspend during shakedown to "fix" a latency observation.
- Skipping masking policy validation because "the policy DDL succeeded".
- Running shakedown without a distinct `QUERY_TAG` so artifacts cannot be recovered from `QUERY_HISTORY`.

### Reference Canary SQL

Reference Snowflake shakedown SQL executed under the application service role with a distinct `QUERY_TAG` for artifact recovery:

```sql
-- Shakedown: post-DDL integration validation against the live account
ALTER SESSION SET QUERY_TAG = 'shakedown:2026-02-05:canary';
USE ROLE app_service_role;
USE WAREHOUSE shakedown_wh;
USE DATABASE shakedown_db;
USE SCHEMA canary;

-- 1. Warehouse resume
SELECT CURRENT_WAREHOUSE(), CURRENT_TIMESTAMP();
SELECT * FROM TABLE(INFORMATION_SCHEMA.WAREHOUSE_LOAD_HISTORY(
    DATE_RANGE_START => DATEADD('minute', -5, CURRENT_TIMESTAMP()),
    WAREHOUSE_NAME   => 'SHAKEDOWN_WH'));

-- 2. View compilation (LIMIT 0 forces compile without materialization)
SELECT * FROM canary.v_canary_active_users LIMIT 0;
SELECT * FROM canary.sv_canary_pii_masked LIMIT 0;

-- 3. Stream capture
INSERT INTO canary.source_table (id, payload) VALUES (1001, 'shakedown-canary');
SELECT METADATA$ACTION, id, payload FROM canary.source_stream;

-- 4. Task manual fire
EXECUTE TASK canary.t_canary_task;
SELECT name, state, error_message
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
    TASK_NAME => 'T_CANARY_TASK'))
ORDER BY scheduled_time DESC
LIMIT 1;

-- 5. Snowpipe ingest
-- (canary file already PUT to @canary.canary_stage/canary.csv)
SELECT SYSTEM$PIPE_STATUS('canary.p_canary_pipe');
SELECT COUNT(*) FROM canary.pipe_target WHERE source_file = 'canary.csv';

-- 6. Masking policy check
SELECT email FROM canary.user_pii WHERE id = 1001;
-- expected: masked string under app_service_role, raw value under pii_admin_role

-- 7. Pruning effectiveness
EXPLAIN USING JSON
SELECT * FROM canary.clustered_events WHERE event_date = '2026-02-05';
-- expected: partitionsScanned is far less than partitionsTotal

-- 8. Cleanup
DELETE FROM canary.source_table WHERE id = 1001;
DELETE FROM canary.pipe_target WHERE source_file = 'canary.csv';
ALTER SESSION UNSET QUERY_TAG;
```

---
[Back to Overview](./OVERVIEW.md)
