# Connection and Resource Management

### Connection Pooling

- Use connection pooling in all application environments; creating connections is expensive.
- Size pools based on workload: too small causes wait times; too large exhausts database connections.
- Configure idle timeout to release unused connections.
- Monitor pool utilization; alert on exhaustion or wait time spikes.

**Pool sizing guidelines:**

- Start with `pool_size = (2 × CPU cores) + disk spindles`.
- Adjust based on measured wait times and utilization.
- Maximum pool size should not exceed `database max_connections / number_of_app_instances`.
- Consider separate pools for transactional and reporting workloads.

### Timeout Configuration

- Set connection timeout to fail fast when database is unavailable (5–10 seconds).
- Set command/query timeout based on expected execution time; don't allow runaway queries to hold connections.
- Read replicas may have higher timeouts to accommodate replication lag.
- Configure statement-level timeouts as a backstop for application-level timeouts.

```sql
-- PostgreSQL session timeouts
SET statement_timeout = '30s';
SET lock_timeout = '5s';

-- SQL Server query timeout (configured in connection/command)
-- ADO.NET: SqlCommand.CommandTimeout = 30;
```

### Resource Limits

- Configure query timeouts at database level as a backstop.
- Set memory limits per query/session to prevent single queries from exhausting resources.
- Use resource governor (SQL Server) or resource limits (PostgreSQL) for workload isolation.
- Configure `max_parallel_workers_per_gather` to limit parallelism (PostgreSQL).

### Connection Strings

- Use encrypted connection strings in configuration.
- Specify application name in connection string for diagnostic visibility.
- Enable connection encryption explicitly; don't rely on server defaults.
- Specify failover partners or read replicas in connection string where applicable.

```text
Server=db.example.com;Database=app_db;User Id=app_user;Password=***;
Encrypt=true;TrustServerCertificate=false;
Application Name=OrderService;
Connect Timeout=5;Command Timeout=30;
MultipleActiveResultSets=false;
```

### Session Configuration Consistency

- Enforce consistent session settings across all application connections (collation, timezone handling, ANSI settings where applicable).
- For engines that support it, set defaults at the database level and validate at connection startup.

```sql
-- SQL Server: Recommended session settings for consistency
SET ANSI_NULLS ON;
SET ANSI_PADDING ON;
SET ANSI_WARNINGS ON;
SET ARITHABORT ON;
SET QUOTED_IDENTIFIER ON;
SET CONCAT_NULL_YIELDS_NULL ON;
```

### Connection Leak Prevention

- Ensure connections are properly disposed in all code paths (finally blocks, using statements).
- Monitor for connections that exceed expected lifetime.
- Set connection lifetime limits to periodically cycle connections.
- Alert on connection count approaching `max_connections`.

---
[Back to Overview](./OVERVIEW.md)
