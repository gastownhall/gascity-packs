# Core Principles

This guide defines strict, practical criteria for selecting the right data storage or messaging technology for each use case. The goal is eliminating ambiguity in technology decisions, preventing architectural mistakes that require expensive migrations, and ensuring each component uses the technology that matches its access patterns.

- **Right Tool for the Job**: No single technology solves all problems; each has specific strengths and trade-offs
- **Access Pattern Alignment**: Storage technology must match how data is read, written, and queried
- **Consistency Requirements**: Understand CAP theorem implications for each choice
- **Operational Cost Awareness**: Factor in not just price, but operational complexity, monitoring, and failure modes
- **Future-Proofing Without Over-Engineering**: Choose for current needs with awareness of scaling paths

### Primary Rule: Start with Requirements, Not Technology

Never begin with "we should use Cosmos DB" or "let's add Redis." Begin with:
- What are the access patterns? (Read-heavy, write-heavy, mixed)
- What are the consistency requirements? (Strong, eventual, none)
- What is the data structure? (Relational, document, key-value, time-series, blob)
- What is the scale? (Megabytes, gigabytes, terabytes, petabytes)
- What are the latency requirements? (Milliseconds, seconds, minutes)
- What is the durability requirement? (Can we lose data? For how long?)
- What is the query complexity? (Simple lookups, complex joins, full-text search, analytics)

### Secondary Rule: Complexity Has Ongoing Costs

Every technology added to the stack increases:
- Operational burden (monitoring, alerting, runbooks)
- Cognitive load (developers must understand it)
- Failure surface area (more things that can break)
- Integration complexity (more connection strings, more SDKs)

A simpler architecture with fewer technologies is preferable to a "perfect" architecture that uses six different storage engines. Only add complexity when requirements demand it.

### Tertiary Rule: Migrations Are Expensive

Choosing the wrong storage technology creates technical debt that compounds. Migrating from one database to another is one of the most expensive and risky operations in software development. Invest time upfront to understand requirements and make the right choice.

---
[Back to Overview](./OVERVIEW.md)
