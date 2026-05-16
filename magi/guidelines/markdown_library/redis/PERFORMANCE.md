# Performance Optimization

### Pipelining

Send multiple commands without waiting for individual responses. Without pipeline: `Send → Wait → Receive → Send → Wait → Receive...`. With pipeline: `Send → Send → Send → Wait → Receive → Receive → Receive`.

Benefit: dramatically reduces round-trip overhead. Batch size: 100–1000 commands per pipeline.

### Lua Scripting

Execute scripts atomically on the server. Benefits: atomic multi-command operations, reduced network round trips, complex logic executes server-side. Use `EVALSHA` after first `EVAL` to cache script SHA.

### Large Value Handling

Large values (>10KB) create problems: increased serialization latency, network bandwidth consumption, memory fragmentation.

Solutions: compress (gzip, LZ4); split into chunks (`largedata:chunk:0`, `largedata:chunk:1`); store reference in Redis with actual data in blob storage; reconsider whether the full object is needed.

### Hot Key Mitigation

Single key receiving disproportionate traffic. Symptoms: single shard CPU spike, increased latency for that key, potential connection exhaustion.

| Solution | Behavior |
|:---------|:---------|
| Local caching | Cache hot key in application memory |
| Read replicas | Distribute reads across replicas (requires client support) |
| Key sharding | Split `counter` into `counter:0`, `counter:1`, … `counter:N`; aggregate client-side |
| Rate limiting | Throttle requests to hot key |

### Connection Efficiency

- **Multiplexing** — clients that multiplex commands over a single connection.
- **Connection reuse** — pool connections; never create per-request.
- **Idle connections** — configure timeouts; don't hold connections unnecessarily.
- **Keep-alive** — enable TCP keep-alive to detect dead connections.

---
[Back to Overview](./OVERVIEW.md)
