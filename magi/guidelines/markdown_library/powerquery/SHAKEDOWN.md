# Post-Rebuild Shakedown

### Definition

A Power Query shakedown is the **controlled refresh against a known-good sample dataset** that confirms every applied step resolves, the output table shape matches expectation, row counts stay within declared bounds, query folding still folds on the rewritten query, and gateway credentials resolve end to end.

**Shakedown executes against a connected source, never against cached in-memory data.**

### Shakedown vs Preflight vs Testing

| Phase | Question Answered |
|:------|:------------------|
| Preflight | Does the PBIP open? Do parameters resolve? Is the gateway online? |
| **Shakedown** | **Does the freshly rebuilt query refresh against the real source and produce the expected shape?** |
| Testing | Behavior, performance, data quality at full volume |

### Mandatory Triggers

- Any edit to an M query, applied step list, or column type declaration.
- Data source URL, database name, or authentication method change.
- Parameter default change affecting query binding.
- Custom function (`fn_*`) create, rename, or signature change.
- Incremental refresh policy create or modify.
- Privacy level change on any source.
- Gateway cluster change or credential rotation.
- Power BI Desktop, Fabric, or on-premises data gateway version upgrade.
- Dataflow Gen1 → Gen2 migration or deployment pipeline promotion.

### Non-Triggers

- Report page or visual layout changes that do not touch M.
- DAX measure edits that do not alter the underlying query.
- Theme or formatting changes.
- Scheduled refresh time adjustments that do not change credentials.

### Validation Categories

Each category exercised against a fixed sample dataset bound through a shakedown parameter switch.

1. **Refresh success** — full query chain refreshes to completion without raising an M error, gateway error, or credential prompt.
2. **Applied steps resolution** — every step resolves without an error indicator. A step that produces an `Error` value in any row is a **blocking failure**.
3. **Output shape** — `Table.ColumnNames` and `Table.Schema` match a declared expected column list and type list exactly. An unexpected column, missing column, or type drift is **blocking**.
4. **Row count bounds** — `Table.RowCount` is within declared min and max bounds for the canary sample. A row count of zero against a non-empty sample is **blocking**.
5. **Join match counts** — for every `Table.NestedJoin` / `Table.Join`, the matched row count is compared against the declared expected count. A silent inner-join-induced row loss is **blocking**.
6. **Privacy level resolution** — refresh completes without a Formula.Firewall error.
7. **Incremental refresh partitions** — if configured, each canary partition (current, previous, historical) loads independently and `RangeStart`/`RangeEnd` parameters bind correctly.
8. **Query folding preservation** — `Value.Metadata` on the final step (or the Diagnose step trace) confirms the source-connected portion still folds. **A lost fold relative to the prior baseline is blocking** for source-connected queries.
9. **Gateway credential resolution** — for gateway-bound sources, refresh runs under the gateway (not via Power BI Desktop credentials) and the gateway log records a successful credential resolution.

### Execution Principles

- **Conservative execution** — sample dataset is small, bounded, representative, never a full production extract.
- **Progressive stress** — refresh one staging query first, then transform tier, then output tier; stop at the first failure.
- **Controlled environment** — dedicated Shakedown workspace or a parameter-driven switch that forces the sample data source.
- **Observable execution** — Query Diagnostics enabled for the full shakedown refresh; trace exported; Diagnose step output preserved.
- **Known-good inputs** — sample dataset versioned alongside the PBIP; updated only via deliberate change that itself triggers a new shakedown.
- **No optimization during shakedown** — folding regression or step slowness logged as non-blocking; rewrites that "fix" it are a separate change.

### Execution Pattern

| Step | Action |
|:----:|:-------|
| 1 | Confirm preflight: PBIP opens, parameters resolve, gateway online, sample data source reachable |
| 2 | Switch the environment parameter to the shakedown sample source |
| 3 | Enable Query Diagnostics (Session and Step) |
| 4 | Refresh a single staging query (`stg_*`); confirm completion without errors |
| 5 | Refresh a single transform query (`tfm_*`); confirm completion without errors |
| 6 | Refresh the full model; confirm completion without errors |
| 7 | Run output-shape, row-count, and join-match-count assertions as M expressions in a shakedown validation query |
| 8 | Inspect the Diagnose trace for fold loss on source-connected steps |
| 9 | If incremental refresh is configured, trigger each partition range and confirm independent success |
| 10 | Verify the gateway log shows a successful credential resolution under the production service account |
| 11 | Switch the environment parameter back to production; confirm no residual cached state remains |
| 12 | Classify the result per validation category |

### Result Classification

- **Pass** — every category completes with the expected shape, row counts, and join match counts; Diagnose trace confirms fold preservation.
- **Fail-blocking** — refresh errors; applied step returns Error rows; output column or type drifts; join silently drops rows; privacy firewall blocks the refresh; folding lost on a source-connected step.
- **Fail-nonblocking** — step-level latency regression or `Table.Buffer` usage increase that does not alter correctness; logged for a subsequent tuning change.
- **Inconclusive** — transient gateway timeout, source-side rate limit, or sample dataset drift prevented a category from completing; re-run the specific category before declaring shakedown failed.

### Required Artifacts

- **Execution log** — Query Diagnostics export covering the full shakedown refresh with per-step duration, fold status, and row counts.
- **Result summary** — pass/fail classification per validation category with shape and row count figures.
- **Issue list** — every non-blocking anomaly with the Diagnose step reference and the originating M edit.
- **Environment snapshot** — Power BI Desktop version, gateway version, M query text hash, parameter values, sample dataset version, workspace identifier at the time of shakedown.

### Anti-Patterns (Forbidden)

- Skipping shakedown after a "small" applied step reorder because "the output looks the same".
- Running shakedown against an in-Desktop cached preview instead of a real refresh against the source.
- Validating join behavior by eyeballing a preview instead of asserting row counts.
- Rewriting a query to "restore folding" during shakedown instead of logging the regression and opening a new change.
- Running shakedown without enabling Query Diagnostics.
- Validating Desktop-only refresh when the production refresh runs through a gateway.
- Treating a Formula.Firewall error as a shakedown pass with a workaround.

### Reference Shakedown Validation Query

```powerquery
let
    // Parameters are switched to the shakedown sample source before this query runs
    Source = tfm_orders,

    // 1. Output shape assertion
    ExpectedColumns = {"OrderID", "CustomerID", "OrderDate", "Amount", "Status"},
    ExpectedTypes   = {Int64.Type, Int64.Type, type date, Decimal.Type, type text},
    ActualColumns   = Table.ColumnNames(Source),
    MissingCols     = List.Difference(ExpectedColumns, ActualColumns),
    ExtraCols       = List.Difference(ActualColumns, ExpectedColumns),
    ShapeCheck =
        if List.Count(MissingCols) > 0 then
            error "Shakedown shape fail - missing columns: " & Text.Combine(MissingCols, ", ")
        else if List.Count(ExtraCols) > 0 then
            error "Shakedown shape fail - unexpected columns: " & Text.Combine(ExtraCols, ", ")
        else Source,

    // 2. Row count bound assertion
    RowCount        = Table.RowCount(ShapeCheck),
    ExpectedMinRows = 100,
    ExpectedMaxRows = 500,
    RowCountCheck =
        if RowCount < ExpectedMinRows or RowCount > ExpectedMaxRows then
            error "Shakedown row count fail - expected " & Text.From(ExpectedMinRows) & " to " & Text.From(ExpectedMaxRows) & ", got " & Text.From(RowCount)
        else ShapeCheck,

    // 3. Join match count assertion (canary customers expected to match exactly)
    JoinedWithCustomers = Table.NestedJoin(RowCountCheck, {"CustomerID"}, stg_customers, {"CustomerID"}, "Customer", JoinKind.LeftOuter),
    Unmatched           = Table.SelectRows(JoinedWithCustomers, each Table.IsEmpty([Customer])),
    JoinCheck =
        if Table.RowCount(Unmatched) > 0 then
            error "Shakedown join fail - unmatched customer rows: " & Text.From(Table.RowCount(Unmatched))
        else JoinedWithCustomers,

    // 4. Folding preservation (Value.Metadata on the source-connected portion)
    FoldMeta = Value.Metadata(Value.ReplaceType(stg_orders, Value.Type(stg_orders))),
    FoldCheck =
        if Record.HasFields(FoldMeta, "QueryFolding") and FoldMeta[QueryFolding] = "Folded" then
            JoinCheck
        else
            error "Shakedown folding fail - source-connected portion no longer folds",

    // 5. Final pass marker
    Result = Table.AddColumn(FoldCheck, "ShakedownStatus", each "PASS", type text)
in
    Result
```

---
[Back to Overview](./OVERVIEW.md)
