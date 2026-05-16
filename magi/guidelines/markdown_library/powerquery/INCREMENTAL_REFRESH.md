# Incremental Refresh

### Required Parameters

```powerquery
// RangeStart parameter
#datetime(2024, 1, 1, 0, 0, 0) meta [
    IsParameterQuery = true,
    Type = "DateTime",
    IsParameterQueryRequired = true
]

// RangeEnd parameter
#datetime(2025, 1, 1, 0, 0, 0) meta [
    IsParameterQuery = true,
    Type = "DateTime",
    IsParameterQueryRequired = true
]
```

Both `RangeStart` and `RangeEnd` parameters of type `DateTime` are mandatory for incremental refresh configuration.

### Incremental Refresh Filtering

```powerquery
let
    Source = Sql.Database("server", "database"),
    FilteredRows = Table.SelectRows(Source, each
        [ModifiedDate] >= RangeStart and
        [ModifiedDate] <  RangeEnd)
in
    FilteredRows
```

### Refresh Policy Configuration

| Setting | Typical Value |
|:--------|:--------------|
| Store Rows | Last 3 years |
| Refresh Rows | Last 10 days |
| Detect Data Changes | Optional watermark column |
| Only Refresh Complete Days | Enabled for daily granularity |

Configure in Power BI Service after publishing.

---
[Back to Overview](./OVERVIEW.md)
