# Indexing Configuration

### Default Indexing

By default, Cosmos DB indexes every property in every document. This enables flexible querying but:
- Consumes storage (indexes can be 10-30% of data size)
- Increases write RU cost (every write updates indexes)
- Indexes properties never queried

### Selective Indexing

Include only queried paths:

```json
{
  "indexingMode": "consistent",
  "automatic": true,
  "includedPaths": [
    { "path": "/type/?" },
    { "path": "/tenantId/?" },
    { "path": "/createdAt/?" },
    { "path": "/status/?" }
  ],
  "excludedPaths": [
    { "path": "/*" }
  ]
}
```

### Exclude Heavy Paths

Exclude write-heavy, never-queried paths:

```json
{
  "indexingMode": "consistent",
  "automatic": true,
  "includedPaths": [
    { "path": "/*" }
  ],
  "excludedPaths": [
    { "path": "/largePayload/*" },
    { "path": "/rawData/*" },
    { "path": "/\"_etag\"/?" }
  ]
}
```

### Composite Indexes

Required for:
- `ORDER BY` on multiple properties
- Filters on multiple properties (improves efficiency)
- Mixed equality and range filters

```json
{
  "compositeIndexes": [
    [
      { "path": "/tenantId", "order": "ascending" },
      { "path": "/createdAt", "order": "descending" }
    ],
    [
      { "path": "/type", "order": "ascending" },
      { "path": "/status", "order": "ascending" },
      { "path": "/priority", "order": "descending" }
    ]
  ]
}
```

Order composite index paths by:
1. Equality filters first
2. Range filters second
3. ORDER BY properties last (matching sort direction)

### Spatial Indexes

```json
{
  "spatialIndexes": [
    {
      "path": "/location/*",
      "types": ["Point", "Polygon"]
    }
  ]
}
```

### Index Transformation

Indexing policy changes trigger background index transformation:
- **Adding paths**: New writes indexed immediately; background process indexes existing documents
- **Removing paths**: Immediate write cost reduction; background process removes existing index entries
- Monitor transformation progress via Azure Portal or REST API
- Large containers may take **hours** to transform

---
[Back to Overview](./OVERVIEW.md)
