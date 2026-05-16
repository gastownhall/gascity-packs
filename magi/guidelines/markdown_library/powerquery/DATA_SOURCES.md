# Data Source Connectivity

### SQL Server / Azure SQL

```powerquery
Sql.Database("server", "database", [CommandTimeout = #duration(0, 0, 30, 0)])
```

- Use the native SQL connector with query folding.
- Use `Value.NativeQuery` only when folding is impossible and source query is necessary.
- Connection parameters: `CommandTimeout`, `MaxConnections`.

### REST APIs

```powerquery
Web.Contents(baseUrl, [
    Headers = [#"Authorization" = "Bearer " & token],
    Query   = [page = "1", limit = "100"],
    Timeout = #duration(0, 0, 2, 0)
])
```

- Implement pagination handling via recursive functions or `List.Generate`.
- Respect rate limits through parameter-controlled delays.
- Cache authentication tokens when possible.

### Files (CSV, Excel, JSON)

- Use folder connectors for multiple files with consistent schema.
- Apply Combine Files transformation for automatic schema inference.
- Filter files by metadata (date modified, name pattern) before combining.
- Handle encoding explicitly; default UTF-8 assumption fails on legacy files.

### SharePoint / OneDrive

- Use SharePoint folder connector for file collections.
- Authenticate via organizational account; service principals for scheduled refresh.
- Account for throttling on large libraries.
- Filter by folder path before expanding contents.

### OData

- Leverage built-in query folding for OData sources.
- Use `OData.Feed` with explicit `Query` option for server-side filtering.
- Handle pagination automatically via `Implementation` option.

### Credential Management

| Forbidden | Required |
|:----------|:---------|
| Hardcoded credentials in queries | Parameters for connection strings |
| Stored passwords in parameters | Credentials managed by gateway or service |
| Embedded API keys in code | Organizational accounts for authentication |
| | Service principals for scheduled refresh |

**Document required permissions** — specify minimum required access levels for each source. **Separate environments** — development, staging, and production use distinct credential sets via parameters.

### Gateway Configuration

| Type | Use For | Constraints |
|:-----|:--------|:------------|
| **Standard gateway** | Most scenarios — shared infrastructure | Max 1000 concurrent connections, 30 min timeout per query |
| Personal gateway | User-specific | Not supported for shared datasets |
| **VNet gateway** | Azure VNet integration for private endpoints | Requires Azure VNet connectivity |

Design queries assuming gateway execution:

- Minimize concurrent connections.
- Avoid operations that require interactive authentication.
- **Test refresh behavior in Service, not just Desktop.**

---
[Back to Overview](./OVERVIEW.md)
