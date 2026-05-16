# Transformation Patterns

### Filtering

```powerquery
// Simple
Table.SelectRows(Source, each [Status] = "Active")

// Multiple conditions (AND)
Table.SelectRows(Source, each [Status] = "Active" and [Amount] > 100)

// Multiple conditions (OR)
Table.SelectRows(Source, each [Category] = "A" or [Category] = "B")

// List membership
Table.SelectRows(Source, each List.Contains({"A", "B", "C"}, [Category]))

// Null handling
Table.SelectRows(Source, each [Value] <> null and [Value] <> "")

// Date range
Table.SelectRows(Source, each [OrderDate] >= prm_StartDate and [OrderDate] <= prm_EndDate)

// Complex compound
Table.SelectRows(Source, each
    [Status] = "Active" and
    [Amount] > 100 and
    List.Contains({"A", "B", "C"}, [Category]) and
    [Date] >= Date.AddMonths(Date.From(DateTime.LocalNow()), -3)
)
```

### Column Operations

```powerquery
// Selection — keep specified columns
Table.SelectColumns(Source, {"CustomerID", "CustomerName", "Revenue"})

// Removal — drop specified columns
Table.RemoveColumns(Source, {"TempColumn", "DebugField"})

// Renaming
Table.RenameColumns(Source, {{"OldName", "NewName"}, {"AnotherOld", "AnotherNew"}})

// Reordering
Table.ReorderColumns(Source, {"ID", "Name", "Date", "Amount"})

// Calculated column
Table.AddColumn(Source, "TotalAmount", each [Quantity] * [UnitPrice], Decimal.Type)
```

### Grouping and Aggregation

```powerquery
// Single aggregation
Table.Group(Source, {"Category"}, {{"TotalRevenue", each List.Sum([Revenue]), type number}})

// Multi-level aggregation
Table.Group(Source, {"Category", "Region"}, {
    {"TotalRevenue", each List.Sum([Revenue]), type number},
    {"AvgAmount", each List.Average([Amount]), type number},
    {"RowCount", each Table.RowCount(_), Int64.Type},
    {"MinDate", each List.Min([Date]), type date},
    {"MaxDate", each List.Max([Date]), type date},
    {"Details", each _, type table}
})

// Returning tables (advanced)
Table.Group(Source, {"CustomerID"}, {{"AllOrders", each _, type table}})
```

### Joins

```powerquery
// Inner
Table.NestedJoin(Orders, {"CustomerID"}, Customers, {"CustomerID"}, "CustomerData", JoinKind.Inner)

// Left outer
Table.NestedJoin(Orders, {"CustomerID"}, Customers, {"CustomerID"}, "CustomerData", JoinKind.LeftOuter)

// Expanding joined columns
Table.ExpandTableColumn(JoinedTable, "CustomerData", {"CustomerName", "Region"})

// Multi-column join
Table.NestedJoin(Source1, {"Key1", "Key2"}, Source2, {"Key1", "Key2"}, "Matched", JoinKind.Inner)
```

### Pivot and Unpivot

```powerquery
// Pivot (rows to columns)
Table.Pivot(Source, List.Distinct(Source[Category]), "Category", "Value", List.Sum)

// Unpivot all non-key columns
Table.UnpivotOtherColumns(Source, {"ID", "Name"}, "Attribute", "Value")

// Unpivot selected columns only
Table.Unpivot(Source, {"Jan", "Feb", "Mar"}, "Month", "Amount")

// Dynamic pivot
let
    Source = InputTable,
    DistinctValues = List.Distinct(Source[Category]),
    Pivoted = Table.Pivot(Source, DistinctValues, "Category", "Value", List.Sum)
in
    Pivoted
```

### Conditional Logic

```powerquery
// Conditional column
Table.AddColumn(Source, "Tier", each
    if [Revenue] >= 100000 then "Enterprise"
    else if [Revenue] >= 10000 then "Mid-Market"
    else "SMB",
    type text)

// Replace values conditionally
Table.ReplaceValue(Source, null, 0, Replacer.ReplaceValue, {"Amount"})

// Multiple replacements
Table.ReplaceValue(Source,
    each [Status],
    each if [Status] = "A" then "Active" else if [Status] = "I" then "Inactive" else [Status],
    Replacer.ReplaceValue,
    {"Status"})
```

---
[Back to Overview](./OVERVIEW.md)
