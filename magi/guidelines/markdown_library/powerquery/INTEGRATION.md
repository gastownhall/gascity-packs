# Integration Patterns

### Power BI

- **Direct Query mode** — Power Query applies only to Import mode. Direct Query bypasses M entirely; transformations must occur at source.
- **Incremental refresh** — see §13.
- **Composite models** — combine Import and Direct Query tables; Power Query applies to Import portions only.

### Excel

Same M engine; different UI and capability constraints:

- Limited connector certification.
- No scheduled refresh without Power BI.
- Local file path handling differs.
- Excel Power Pivot has distinct limitations from Power BI data models.

### Dataflows

- **Gen1** — shared Power Query logic across multiple Power BI datasets; staged storage in Azure Data Lake or CDM folders.
- **Gen2 (Fabric)** — enhanced orchestration and compute scaling; integration with Fabric pipelines; Direct Lake mode for optimized storage.

### Azure

```powerquery
// Azure Data Lake
AzureStorage.DataLake("https://account.dfs.core.windows.net/container")

// Azure SQL with AAD authentication
Sql.Database("server.database.windows.net", "database", [Authentication = "ActiveDirectory"])
```

**Azure Synapse** — same connectors as SQL Server; use dedicated SQL pool connector for optimized performance.

### Fabric

- **Lakehouse connectivity** — direct access to Fabric lakehouse tables and files.
- **Warehouse connectivity** — SQL endpoint access with query folding.
- **Semantic model refresh** — Power Query feeds semantic models (formerly datasets) with scheduled refresh orchestration.

---
[Back to Overview](./OVERVIEW.md)
