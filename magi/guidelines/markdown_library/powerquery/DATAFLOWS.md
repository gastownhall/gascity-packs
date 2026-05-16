# Dataflow Patterns

### Architecture

**Staging dataflow** — raw extraction:

```powerquery
let
    Source   = SharePoint.Files("https://tenant.sharepoint.com", [ApiVersion = 15]),
    Filtered = Table.SelectRows(Source, each [Extension] = ".csv"),
    Combined = Table.Combine(Filtered[Content])
in
    Combined
```

**Linked entities** — reference dataflow entities downstream:

```powerquery
let
    Source    = PowerPlatform.Dataflows([]),
    Workspace = Source{[workspaceName="Analytics"]}[Data],
    Entity    = Workspace{[entity="dim_customer"]}[Data]
in
    Entity
```

**Computed entities** — transform linked entities with enhanced compute:

```powerquery
let
    Source = LinkedEntity_Customer,
    Enriched = Table.AddColumn(Source, "Segment", each
        if [TotalRevenue] > 100000 then "Enterprise"
        else if [TotalRevenue] > 10000 then "Mid-Market"
        else "SMB"
    )
in
    Enriched
```

### Dataflow Refresh Strategy

| Layer | Schedule |
|:------|:---------|
| Staging dataflow | 02:00 |
| Transformation dataflow | 03:00 |
| Analytical dataset | 04:00 |

- Staging dataflows refresh **before** transformation dataflows.
- Datasets refresh **after** all dependent dataflows complete.

### Linked vs Computed Entities

| Type | Behavior |
|:-----|:---------|
| Linked | Reference to source dataflow entity; refresh depends on source |
| Computed | Transformation on linked entity; separate refresh schedule |

---
[Back to Overview](./OVERVIEW.md)
