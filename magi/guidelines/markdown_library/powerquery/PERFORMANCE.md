# Performance Optimization

### Query Evaluation Model

Power Query's lazy evaluation:

- Steps only execute when their output is required.
- Unused columns may never be computed.
- Buffering explicitly materializes data at a step.

### Buffer Strategies

| Function | Purpose |
|:---------|:--------|
| `Table.Buffer` | Materializes table in memory; subsequent references use cached copy |
| `List.Buffer` | Materializes list in memory; for repeated list operations |

Use buffer when:

- Same table referenced multiple times in one query.
- Preventing re-execution of expensive source queries.
- Breaking query folding intentionally (to cache results).

```powerquery
let
    // Buffer only when table is accessed multiple times
    Source = Table.Buffer(ExpensiveSourceQuery),
    Join1  = Table.NestedJoin(Orders,  {"CustomerID"}, Source, {"ID"}, "Customer1"),
    Join2  = Table.NestedJoin(Returns, {"CustomerID"}, Source, {"ID"}, "Customer2")
in
    [Orders = Join1, Returns = Join2]
```

**Avoid excessive buffering** — each buffer consumes memory; buffer only when repeated access is confirmed.

### Streaming vs Materialization

Operations requiring full materialization:

- Sorting (`Table.Sort`).
- Aggregation (`Table.Group`).
- Distinct operations (`Table.Distinct`).
- Joins in some configurations.

Design queries to defer materialization; filter and select before operations requiring full scans.

### Parallel Evaluation

```powerquery
// Independent queries execute in parallel
let
    Customers = stg_customers,
    Products  = stg_products,
    Orders    = stg_orders,
    // This waits for all three to complete
    Combined = Table.Combine({Customers, Products, Orders})
in
    Combined
```

Independent staging queries execute concurrently. Single monolithic queries cannot parallelize.

### Memory Management — Batch Processing

```powerquery
let
    BatchSize  = 10000,
    RowCount   = Table.RowCount(Source),
    BatchCount = Number.RoundUp(RowCount / BatchSize),
    Batches    = List.Generate(
        () => 0,
        each _ < BatchCount,
        each _ + 1,
        each Table.Range(Source, _ * BatchSize, BatchSize)
    ),
    Processed = List.Transform(Batches, each ProcessBatch(_)),
    Combined  = Table.Combine(Processed)
in
    Combined
```

### Diagnostics and Profiling

| Step | Action |
|:----:|:-------|
| 1 | Tools → Start Diagnostics |
| 2 | Refresh queries |
| 3 | Stop diagnostics |
| 4 | Analyze diagnostics tables |

Key metrics:

- **Data Source Query** — time spent at source.
- **Exclusive Duration** — time for that step alone.
- **Row Count** — data volume at each step.
- **Folding Status** — whether operation folded.

### Performance Monitoring Query

```powerquery
let
    DiagnosticsTable = Table.FromRecords({
        [QueryName = "stg_customers", Duration = 120, RowCount = 50000,  Folded = true],
        [QueryName = "tfm_orders",    Duration = 340, RowCount = 125000, Folded = false]
    }),
    AddStatus = Table.AddColumn(DiagnosticsTable, "Status", each
        if [Duration] > 300 then "Slow"
        else if [Duration] > 100 then "Normal"
        else "Fast"
    )
in
    AddStatus
```

### Performance Checklist

- Filter as early as possible in query chain.
- Select only required columns.
- Apply types once at ingestion.
- Avoid nested queries when flat references work.
- Use `Table.Buffer` only when repeated access is needed.
- Verify query folding for all source-connected steps.
- Profile large queries with diagnostics before deployment.

---
[Back to Overview](./OVERVIEW.md)
