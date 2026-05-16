# Post-Change Shakedown

### Definition

A Cosmos DB shakedown is a known-good document round-trip against the **real target account** that validates the live container behaves as declared after any structural change.

Shakedown validates integration of partition key, indexing policy, consistency level, change feed, server-side code, and TTL against the actual account.

Distinction:
- **Preflight** — confirms the account, key, and emulator reachability exist
- **Shakedown** — confirms a document flows through the container correctly
- **Testing** — confirms behavior and RU budgets hold at production scale

### Mandatory Triggers

Shakedown is mandatory after any change that alters container structure or server-side semantics:

- Partition key path change (requires container recreate and data migration)
- Container recreate, split, or throughput model change (manual ↔ autoscale ↔ serverless)
- Indexing policy update (included paths, excluded paths, composite indexes, spatial indexes)
- Consistency level change at account or request scope
- Stored procedure, trigger, or UDF deployment or update
- TTL enablement, disablement, or default change
- Multi-region write topology change or conflict resolution policy change
- SDK major version upgrade or connection mode change (direct ↔ gateway)
- Managed identity, role assignment, or firewall rule change affecting the data plane

### Non-Triggers

- Routine document writes within an unchanged access pattern
- Alert threshold tuning in monitoring
- Client-side retry policy tuning that does not change the connection mode
- Cost reporting or tagging changes that do not touch the data plane

### Validation Categories (Nine Surfaces)

1. **Document round-trip** — Canary document is created, point-read, replaced, upserted, and deleted against the declared partition key path; the partition key value is present and matches the path exactly.
2. **Query path** — Representative SQL query against the current indexing policy returns the canary document and expected projections; cross-partition query is exercised once to confirm it executes within the RU budget declared for the operation.
3. **RU accounting** — `x-ms-request-charge` is captured for every canary operation and compared against the documented RU budget; **a spike over budget is a blocking failure.**
4. **Change feed propagation** — The canary mutation appears in the change feed (latest or all-versions-and-deletes mode, as configured) within the declared latency budget; the lease container is observed to advance.
5. **Server-side code** — Every stored procedure, pre-trigger, post-trigger, and UDF referenced by the application is executed once against the canary document and the return value is inspected for correctness.
6. **Consistency guarantee** — The configured consistency level is exercised: session tokens propagate for session, staleness bound holds for bounded staleness, monotonic read holds for eventual, and strong reflects the latest write before returning.
7. **TTL expiry** — A canary document with explicit `ttl` is written and observed to be removed within the declared TTL window (with a reasonable grace interval); absence is confirmed by a point read returning 404.
8. **Conflict resolution** — For multi-region-write accounts, a deliberate conflicting write is issued against two regions and the configured policy (LWW or custom) is observed to apply; conflict feed inspected if custom.
9. **Authorization path** — The service principal or managed identity used in production executes the canary round-trip; a forbidden operation (write to a read-only container, cross-database read) is confirmed to return 403.

### Execution Principles

- **Conservative execution** — one canary document per validation category; never production data; never stress loads
- **Progressive stress** — start with a single point write, add a query, add the change feed observer, add the stored procedure, stop at the first failure
- **Controlled environment** — dedicated shakedown container (or a canary partition key value) in a non-production database that mirrors production indexing policy, consistency level, and throughput model exactly
- **Observable execution** — every request captures `x-ms-request-charge`, `x-ms-activity-id`, `x-ms-session-token`, end-to-end latency; SDK diagnostic string preserved
- **Known-good inputs** — fixed JSON canary document with known `id` and partition key; expected point-read and query projections pre-declared
- **No optimization during shakedown** — observed RU spikes or latency regressions are logged as non-blocking issues; tuning is deferred to a separate change that itself triggers a new shakedown

### Execution Sequence

```text
Step 1:  Confirm preflight passes — account endpoint reachable, credential resolves, target database and container exist, required role assignments present
Step 2:  Initialize the canary scope — dedicated container or partition key value, lease container for change feed, fixed canary document template loaded
Step 3:  Execute the simplest end-to-end path — create canary, point-read, assert payload equality, delete, confirm 404 on follow-up read
Step 4:  Verify query path — run reference SQL, assert result set, capture RU charge
Step 5:  Verify change feed — write a canary mutation, observe it emerge from the processor within the latency budget
Step 6:  Verify server-side code — execute every referenced stored procedure, trigger, and UDF once and assert return values
Step 7:  Verify consistency guarantee, TTL expiry, and conflict resolution as applicable
Step 8:  Check for orphans — canary leases released, canary documents removed, lease container tombstones observed
Step 9:  Record all RU charges, latencies, activity ids, and diagnostic strings
Step 10: Classify the result per validation category
```

### Result Classification

- **pass** — Every validation category completes within its RU and latency budget and returns the expected payload.
- **fail-blocking** — Any category returns incorrect data, exceeds its RU budget by more than the declared tolerance, returns an unexpected HTTP status, or leaks change feed leases or canary documents.
- **fail-nonblocking** — Observed RU or latency regression that does not alter correctness and stays within operational tolerances. Logged with the full SDK diagnostic string.
- **inconclusive** — A transient 429, 503, or network timeout prevented a category from completing. The specific category is re-run after backoff before the shakedown is declared failed.

### Required Artifacts

- **Execution log** — timestamped log of every canary operation with activity id, RU charge, latency, session token
- **Result summary** — pass/fail per category with RU and latency figures
- **Issue list** — every non-blocking anomaly with its SDK diagnostic string and reproduction context
- **Environment snapshot** — account endpoint, database id, container id, indexing policy, consistency level, throughput model, SDK version, region topology

### Reference Canary Document

```json
{
  "id": "shakedown-canary-0001",
  "pk": "shakedown-tenant",
  "type": "ShakedownCanary",
  "payload": {
    "field_string": "known-good",
    "field_number": 42,
    "field_array": ["a", "b", "c"]
  },
  "ttl": 300,
  "_shakedown": {
    "expected_point_read_ru": 1.0,
    "expected_query_ru_ceiling": 5.0,
    "expected_change_feed_latency_ms": 2000,
    "expected_status_after_ttl": 404
  }
}
```

### Anti-Patterns (Forbidden)

- Skipping shakedown after an indexing policy edit because "it is just an excluded path"
- Treating shakedown as a full load test with thousands of documents instead of a handful of canaries
- Running shakedown against the emulator when production uses multi-region writes or a non-default consistency level
- Adjusting RU provisioning or indexing policy during shakedown to "make the numbers look better"
- Running a canary round-trip without capturing `x-ms-request-charge` or the SDK diagnostic string
- Validating only the create and read path while ignoring change feed, stored procedures, or TTL

---
[Back to Overview](./OVERVIEW.md)
