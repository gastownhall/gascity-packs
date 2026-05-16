# Testing and Validation

### Schema Validation

```powerquery
let
    ExpectedColumns = {"ID", "Name", "Amount", "Date"},
    ActualColumns   = Table.ColumnNames(Source),
    Missing = List.Difference(ExpectedColumns, ActualColumns),
    Extra   = List.Difference(ActualColumns, ExpectedColumns),
    Validation = if List.Count(Missing) > 0 then
        error "Missing columns: " & Text.Combine(Missing, ", ")
    else if List.Count(Extra) > 0 then
        error "Unexpected columns: " & Text.Combine(Extra, ", ")
    else Source
in
    Validation
```

### Data Quality Checks

```powerquery
let
    Source          = stg_orders,
    NullCheck       = Table.SelectRows(Source, each [OrderID] = null),
    DuplicateCheck  = Table.Group(Source, {"OrderID"}, {{"Count", Table.RowCount, Int64.Type}}),
    Duplicates      = Table.SelectRows(DuplicateCheck, each [Count] > 1),
    Validation =
        if Table.RowCount(NullCheck) > 0 then error "Null OrderIDs found"
        else if Table.RowCount(Duplicates) > 0 then error "Duplicate OrderIDs found"
        else Source
in
    Validation
```

### Row Count Validation

```powerquery
let
    CurrentCount     = Table.RowCount(Source),
    ExpectedMinimum  = 1000,
    Validation = if CurrentCount < ExpectedMinimum then
        error "Row count " & Text.From(CurrentCount) & " below minimum " & Text.From(ExpectedMinimum)
    else Source
in
    Validation
```

### Referential Integrity

```powerquery
let
    OrderCustomerIDs = List.Distinct(Orders[CustomerID]),
    CustomerIDs      = List.Distinct(Customers[CustomerID]),
    OrphanedOrders   = List.Difference(OrderCustomerIDs, CustomerIDs),
    Validation = if List.Count(OrphanedOrders) > 0 then
        error "Orphaned CustomerIDs in Orders: " & Text.From(List.Count(OrphanedOrders))
    else Orders
in
    Validation
```

### Function Unit Testing

```powerquery
let
    TestCases = Table.FromRecords({
        [Input = "  test  ",    Expected = "test",         Function = fn_Trim],
        [Input = null,          Expected = null,           Function = fn_SafeUpper],
        [Input = "123-45-6789", Expected = "***-**-6789",  Function = fn_MaskSSN]
    }),
    RunTests   = Table.AddColumn(TestCases, "Result", each [Function]([Input])),
    AddStatus  = Table.AddColumn(RunTests, "Status", each
        if [Result] = [Expected] then "PASS" else "FAIL"
    ),
    FailedTests = Table.SelectRows(AddStatus, each [Status] = "FAIL")
in
    if Table.RowCount(FailedTests) > 0 then
        error "Unit tests failed: " & Text.From(Table.RowCount(FailedTests))
    else AddStatus
```

### Regression Testing

```powerquery
let
    Current      = OutputQuery,
    Baseline     = BaselineSnapshot,
    CurrentHash  = Binary.ToText(Binary.From(Current),  BinaryEncoding.Base64),
    BaselineHash = Binary.ToText(Binary.From(Baseline), BinaryEncoding.Base64),
    Match        = CurrentHash = BaselineHash
in
    if Match then Current else error "Output differs from baseline"
```

---
[Back to Overview](./OVERVIEW.md)
