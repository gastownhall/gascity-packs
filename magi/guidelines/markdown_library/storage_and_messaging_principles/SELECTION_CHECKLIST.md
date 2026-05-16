# Technology Selection Checklist

Before selecting a technology, answer these questions:

### Data Characteristics
- [ ] What is the data structure? (Relational, document, key-value, blob)
- [ ] What is the expected data size? (Now and in 2 years)
- [ ] What is the record size distribution?
- [ ] How frequently does schema change?

### Access Patterns
- [ ] Read/write ratio documented
- [ ] Query patterns documented (by key, by filter, joins)
- [ ] Throughput requirements (reads/sec, writes/sec)
- [ ] Latency requirements (p50, p95, p99)
- [ ] Concurrency requirements (concurrent connections, users)

### Consistency and Durability
- [ ] Consistency requirements documented (strong, eventual, session)
- [ ] Durability requirements documented (can we lose data?)
- [ ] Transaction requirements documented (scope, isolation)

### Operational Requirements
- [ ] Team expertise assessed
- [ ] Operational burden acceptable
- [ ] Monitoring and alerting plan
- [ ] Backup and recovery plan
- [ ] Security requirements met

### Cost
- [ ] Total cost of ownership estimated
- [ ] Cost at 10x scale estimated
- [ ] Comparison with alternatives documented

### Decision Documentation
- [ ] Decision rationale documented
- [ ] Trade-offs acknowledged
- [ ] Migration path considered
- [ ] Review date scheduled

---
[Back to Overview](./OVERVIEW.md)
