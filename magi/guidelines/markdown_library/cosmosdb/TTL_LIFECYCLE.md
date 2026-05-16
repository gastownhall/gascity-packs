# Time-to-Live and Data Lifecycle

### TTL Configuration

Container-level default TTL:
- `-1` or unset: TTL disabled; documents live forever
- `0`: TTL enabled but no default; documents require explicit TTL
- Positive integer: default TTL in seconds for documents without explicit TTL

Document-level TTL:
- `ttl` property on document overrides container default
- `null` or absent: use container default
- `-1`: never expire (even if container has default TTL)
- Positive integer: expire this many seconds after `_ts`

### TTL Use Cases

- Session data: expire after inactivity period
- Cache entries: automatic invalidation
- Temporary data: processing intermediates, uploads in progress
- Compliance: automatic deletion after retention period

### TTL Mechanics

- Expired documents deleted by background process
- **No RU consumption for TTL deletions**
- Deletions **not captured** in Change Feed
- Expired documents may be briefly visible before cleanup

### Archival Pattern

For data requiring long-term retention but not active querying:
1. Write to hot container with short TTL
2. Change Feed processor copies to archive container or blob storage
3. Hot container remains small and performant
4. Query archive for historical data with separate cost profile

---
[Back to Overview](./OVERVIEW.md)
