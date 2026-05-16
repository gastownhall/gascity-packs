# Query Architecture and Organization

### Query Hierarchy

| Tier | Prefix | Purpose |
|:-----|:-------|:--------|
| Parameters | `prm_` | Configuration values that vary by environment or control query behavior |
| Functions | `fn_` | Reusable transformation logic accepting inputs and returning outputs |
| Staging Queries | `stg_` | Raw data extraction with minimal transformation. Apply only source filters and column selection |
| Transformation Queries | `tfm_` | Business logic, joins, calculations, enrichment. Reference staging queries; never duplicate source connections |
| Output Queries | (none) or `dim_` / `fact_` | Final tables loaded to the data model. Only output queries have "Enable Load" checked |

### Folder Organization

```text
├── Parameters
│   ├── prm_Environment
│   ├── prm_StartDate
│   └── prm_SourcePath
├── Functions
│   ├── fn_CleanText
│   ├── fn_ParseDate
│   └── fn_GetApiPage
├── Staging
│   ├── stg_Customers_Raw
│   ├── stg_Orders_Raw
│   └── stg_Products_Raw
├── Transform
│   ├── tfm_Customers_Cleaned
│   ├── tfm_Orders_Enriched
│   └── tfm_Products_Categorized
└── Output
    ├── dim_Customer
    ├── dim_Product
    └── fact_Sales
```

### Query Naming Conventions

- **Lowercase with underscores** — `stg_customer_orders`, not `StgCustomerOrders` or `Stg Customer Orders`.
- **Prefix by purpose** — `prm_`, `fn_`, `stg_`, `tfm_`, `dim_`, `fact_`.
- **Descriptive but concise** — names indicate content and purpose without redundancy.
- **No spaces** — spaces in query names create friction when referencing in M code.
- **Singular for entities** — `dim_customer`, not `dim_customers`. The table contains customer records; each record is a customer.

Forbidden:

- Spaces in query names.
- Default auto-generated names.
- Mixed casing styles.

### Step Naming

Within queries, step names should be meaningful:

- **Descriptive action names** — `FilterActiveCustomers`, `JoinWithRegion`, `CalculateTotalAmount`.
- **Replace default names** — `#"Removed Columns"` → `RemoveMetadataColumns`.
- **PascalCase** for step names.
- Sequential clarity — steps read as a narrative of transformations applied.

```powerquery
let
    Source = Sql.Database("server", "database"),
    FilterActiveCustomers = Table.SelectRows(Source, each [Status] = "Active"),
    SelectRequiredColumns = Table.SelectColumns(FilterActiveCustomers, {"ID", "Name"}),
    ApplyBusinessRules = Table.AddColumn(SelectRequiredColumns, "Category", each ...)
in
    ApplyBusinessRules
```

### Reference vs Duplicate

| Operation | Behavior |
|:----------|:---------|
| **Reference** (`= stg_customers`) | Pointer to another query's output. Changes propagate. **Use for query chaining.** |
| Duplicate | Independent copy of the query definition. Changes do not propagate. Use only when intentionally forking logic. |

**Always prefer references.** Duplicates create maintenance burden and risk divergence.

### Disabling Load

Staging and transformation queries have **Enable Load disabled**. Only final output queries load to the data model. Loading intermediate queries wastes memory, increases refresh time, and clutters the model. Functions and parameters never load regardless of setting.

---
[Back to Overview](./OVERVIEW.md)
