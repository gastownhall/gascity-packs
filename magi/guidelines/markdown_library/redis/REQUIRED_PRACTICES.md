# Required Practices

### Always Do

- Enable TLS for all connections.
- Configure connection pooling with appropriate min/max sizes.
- Set TTL on all cache entries — even long TTL is better than none.
- Use structured key naming with consistent namespace prefixes.
- Monitor memory usage, connection count, and eviction rate.
- Implement retry logic with exponential backoff for transient failures.
- Use hash tags deliberately when multi-key operations required in clusters.
- Test failover behavior before production deployment.
- Document data access patterns and sizing rationale.
- Configure alerts on critical metrics (memory >80%, server load >70%).
- Use async operations where client supports them.
- Implement circuit breakers for cache operations.
- Validate cache hit rates; low hit rate indicates ineffective caching.
- Plan for cache warm-up after restarts or cold deployments.
- Rotate access keys periodically using secondary key for continuity.
- Use private endpoints or VNet integration for production workloads.
- Serialize with versioning; handle schema evolution gracefully.
- Size connection pools based on measured concurrency, not guesses.
- Run a §25 shakedown after every change to ACLs, topology, persistence, eviction policy, TLS, modules, or Lua scripts.

---
[Back to Overview](./OVERVIEW.md)
