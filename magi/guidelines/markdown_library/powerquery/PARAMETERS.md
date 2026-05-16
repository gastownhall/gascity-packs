# Parameter Management

### Parameter Types

| Type | Purpose |
|:-----|:--------|
| Text | Environment URLs, file paths, connection strings |
| Number | Thresholds, limits, page sizes |
| Date | Report start/end dates, as-of dates |
| Logical | Feature flags, mode switches |
| List | Multi-select values, category filters |

### Parameter Definition

```powerquery
// Simple parameter
"Production" meta [
    IsParameterQuery = true,
    Type = "Text",
    IsParameterQueryRequired = true
]

// Parameter with allowed values
"Production" meta [
    IsParameterQuery = true,
    Type = "Text",
    IsParameterQueryRequired = true,
    AllowedValues = {"Development", "Staging", "Production"}
]
```

### Parameter Tables (Centralized)

```powerquery
let
    ParameterTable = Table.FromRecords({
        [Name = "Environment",    Value = "Production",       Type = "Text"],
        [Name = "StartDate",      Value = #date(2025, 1, 1),  Type = "Date"],
        [Name = "BatchSize",      Value = 1000,               Type = "Number"],
        [Name = "EnableLogging",  Value = true,               Type = "Logical"]
    }),
    GetParameter = (paramName as text) =>
        Table.SelectRows(ParameterTable, each [Name] = paramName){0}[Value]
in
    ParameterTable
```

### Environment-Based Configuration

```powerquery
let
    EnvironmentConfig = [
        Development = [
            Server      = "dev-server",
            Database    = "DevDB",
            MaxRows     = 1000,
            EnableDebug = true
        ],
        Staging = [
            Server      = "stg-server",
            Database    = "StgDB",
            MaxRows     = 10000,
            EnableDebug = false
        ],
        Production = [
            Server      = "prd-server",
            Database    = "PrdDB",
            MaxRows     = null,
            EnableDebug = false
        ]
    ],
    CurrentEnv = Record.Field(EnvironmentConfig, prm_Environment),
    Source     = Sql.Database(CurrentEnv[Server], CurrentEnv[Database])
in
    Source
```

### Dynamic Path Construction

```powerquery
let
    BasePath = prm_DataPath,
    FileName = "sales_" & Date.ToText(prm_ReportDate, "yyyyMMdd") & ".csv",
    FullPath = Text.Combine({BasePath, FileName}, "\"),
    Source   = Csv.Document(File.Contents(FullPath))
in
    Source
```

### Parameter Documentation

```powerquery
let
    Parameter = "2025-01-01",
    Documentation = [
        Documentation.Name        = "prm_StartDate",
        Documentation.Description = "Report start date in YYYY-MM-DD format",
        Documentation.AllowedValues = "Any valid date string"
    ]
in
    Date.FromText(Parameter) meta Documentation
```

---
[Back to Overview](./OVERVIEW.md)
