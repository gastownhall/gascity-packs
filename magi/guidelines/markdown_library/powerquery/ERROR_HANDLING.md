# Error Handling

### Error Types

- **Expression errors** — invalid syntax, undefined identifiers, type mismatches.
- **Data errors** — source connectivity failures, authentication, invalid data formats.
- **Evaluation errors** — division by zero, null reference, out-of-range values.

### Try-Otherwise

```powerquery
// Basic
let
    RiskyOperation = try SomeFunctionThatMightFail() otherwise DefaultValue
in
    RiskyOperation

// With error inspection
let
    Result = try SourceQuery,
    Output = if Result[HasError] then
        error Error.Record("DataError", "Source query failed: " & Result[Error][Message])
    else
        Result[Value]
in
    Output
```

### Row-Level Errors

```powerquery
// Safe column operation
Table.AddColumn(Source, "SafeDivision", each
    try [Numerator] / [Denominator] otherwise null,
    type number)

// Error tracking — separate Value and Error columns
let
    AddCalculation = Table.AddColumn(Source, "Result", each try [A] / [B]),
    ExtractValue   = Table.AddColumn(AddCalculation, "Value",
        each if [Result][HasError] then null else [Result][Value]),
    ExtractError   = Table.AddColumn(ExtractValue, "Error",
        each if [Result][HasError] then [Result][Error][Message] else null)
in
    Table.RemoveColumns(ExtractError, {"Result"})
```

### Custom Error Generation

```powerquery
if Table.RowCount(Source) = 0 then
    error Error.Record(
        "EmptyDataError",
        "Source returned no rows",
        [Source = "CustomerTable", RefreshTime = DateTime.LocalNow()]
    )
else Source
```

### Error Logging

```powerquery
let
    TryRefresh = try SourceQuery,
    LogEntry = [
        Timestamp    = DateTime.LocalNow(),
        QueryName    = "stg_customers",
        Success      = not TryRefresh[HasError],
        ErrorMessage = if TryRefresh[HasError] then TryRefresh[Error][Message] else null
    ],
    LogToTable = Table.InsertRows(ErrorLogTable, {LogEntry}),
    Result     = if TryRefresh[HasError] then #table({}, {}) else TryRefresh[Value]
in
    Result
```

### Defensive Patterns

```powerquery
// Null-safe navigation
each if [NestedRecord] = null then null else [NestedRecord][FieldName]

// Empty table handling
if Table.IsEmpty(Source) then
    #table({"ID", "Name"}, {})
else
    Source

// Schema validation before processing
let
    RequiredColumns = {"ID", "Name", "Amount"},
    ActualColumns   = Table.ColumnNames(Source),
    MissingColumns  = List.Difference(RequiredColumns, ActualColumns),
    Validated = if List.Count(MissingColumns) > 0 then
        error "Missing columns: " & Text.Combine(MissingColumns, ", ")
    else Source
in
    Validated
```

---
[Back to Overview](./OVERVIEW.md)
