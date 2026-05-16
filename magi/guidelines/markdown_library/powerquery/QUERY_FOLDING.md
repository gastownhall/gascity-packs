# Query Folding

### Folding Fundamentals

Query folding translates M expressions into source-native queries. When folding occurs:

- Filtering happens at the source; only matching rows transfer.
- Aggregations compute at the source; single result rows transfer.
- Joins execute at the source when both tables come from the same source.
- Column selection limits network transfer to required data.

When folding breaks:

- All subsequent operations execute locally.
- Full datasets must transfer before local processing.
- Performance degrades proportionally to data volume.

### Folding Verification

| Method | How |
|:-------|:----|
| **View Native Query** | Right-click any step. Available = step folds and shows generated SQL/OData. Grayed out = step does not fold |
| **Query Diagnostics** | Tools → Start Diagnostics → refresh → Stop. Review `Folding Status` column and `Data Source Query` |

### Operations That Typically Fold

| Operation | SQL Server | OData | SharePoint | Notes |
|:----------|:-----------|:------|:-----------|:------|
| `Table.SelectRows` | Yes | Yes | Partial | Condition complexity affects folding |
| `Table.SelectColumns` | Yes | Yes | Yes | |
| `Table.Sort` | Yes | Yes | Yes | |
| `Table.FirstN` / `LastN` | Yes | Yes | Yes | |
| `Table.Group` | Yes | Limited | No | OData grouping depends on version |
| `Table.Join` | Yes | No | No | Both tables must be same source |
| `Table.Distinct` | Yes | Yes | No | |
| `Table.TransformColumnTypes` | Yes | Yes | Yes | Type casting folds |

### Operations That Break Folding

- Custom functions applied to columns (`Table.TransformColumns` with M functions).
- List operations on column values (`List.Transform`, `List.Select`).
- Text functions with locale parameters (`Text.Lower` folds; `Text.Lower` with culture does not).
- DateTime operations with time zones (local timezone conversion breaks folding).
- `Table.Buffer` (explicit local materialization).
- `Table.Combine` with heterogeneous sources (cannot fold across source boundaries).
- `try` expressions on source operations (prevents folding).

### Folding Optimization

**Filter early:**

```powerquery
let
    Source = Sql.Database("server", "database"),
    // Good: Filter first to minimize data transfer
    FilteredRows = Table.SelectRows(Source, each [Date] >= Date.StartOfMonth(Date.From(DateTime.LocalNow()))),
    SelectedColumns = Table.SelectColumns(FilteredRows, {"ID", "Name", "Amount"})
in
    SelectedColumns
```

**Restructure for folding:**

```text
// Bad: Folding breaks at step 2, full table scanned
Source → CustomTransform → FilterRows

// Good: Filter folds, reduced data for custom transform
Source → FilterRows → CustomTransform
```

**Use Value.NativeQuery sparingly** — when complex logic cannot fold, push a native query to the source:

```powerquery
Value.NativeQuery(
    Source,
    "SELECT * FROM Orders WHERE Status = @status",
    [status = "Active"]
)
```

Native queries bypass some folding optimizations and create maintenance burden. Use only when M expressions cannot achieve required logic.

---
[Back to Overview](./OVERVIEW.md)
