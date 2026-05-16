# Prohibited Practices

### Never Do

- Use Basic tier in production — no SLA and loses data on maintenance.
- Store passwords, tokens, or secrets as plain text in keys or values.
- Use `KEYS *` in production — blocks the server and scans entire keyspace.
- Create keys without TTL for cached data — memory grows unbounded.
- Create connection per request — pool connections and reuse.
- Store large objects (>1MB) without compression or chunking.
- Use `FLUSHALL` or `FLUSHDB` without explicit confirmation process.
- Assume cache always available — handle cache failures gracefully.
- Mix eviction policies in shared cache without understanding interactions.
- Ignore `evicted_keys` — it indicates memory pressure requiring action.
- Use Redis as primary data store for critical data without persistence-guarantee understanding.
- Deploy without monitoring — blind operation prevents problem detection.
- Use default access keys in code — use secret management.
- Allow public network access without firewall rules.
- Run expensive Lua scripts — they block all other operations.
- Ignore connection limits — exhaustion causes cascading failures.
- Use synchronous operations where async is available — blocking wastes resources.
- Store serialized objects without versioning — schema changes break deserialization.
- Implement distributed locks without TTL — crashed clients cause permanent deadlocks.
- Skip shakedown after ACL, topology, persistence, eviction-policy, TLS, or module changes.

---
[Back to Overview](./OVERVIEW.md)
