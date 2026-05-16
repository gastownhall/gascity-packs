# Access Pattern Analysis

Before selecting a technology, document the access patterns:

### Questions to Answer

1. **Read/Write Ratio**: What percentage of operations are reads vs writes?
2. **Query Complexity**: Simple lookups by key, or complex queries with filters/joins?
3. **Consistency Requirements**: Must reads always see latest write? Acceptable staleness window?
4. **Latency Requirements**: What is the acceptable p99 latency for reads? Writes?
5. **Throughput Requirements**: Expected operations per second at peak?
6. **Data Size**: Total dataset size? Individual record size?
7. **Data Lifespan**: How long must data be retained? Can old data be deleted/archived?
8. **Access Locality**: Is data accessed by a natural partition (tenant, user, region)?

### Access Pattern Categories

**Key-Value Lookup**:
- Access by single key
- No complex queries
- Best: Redis (cache), Cosmos DB (persistent), Table Storage (cheap)

**Document Retrieval**:
- Access hierarchical/nested data
- Query by document properties
- Best: Cosmos DB, MongoDB

**Relational Queries**:
- JOINs across entities
- Complex WHERE clauses
- Aggregations, GROUP BY
- Best: SQL Server, PostgreSQL

**Time-Series**:
- Write-heavy, append-only
- Query by time range
- Aggregation over time windows
- Best: Time-series database, Cosmos DB (with time-based partition), Azure Data Explorer

**Full-Text Search**:
- Search within text content
- Relevance ranking
- Faceted search
- Best: Elasticsearch, Azure Cognitive Search, PostgreSQL full-text

**Analytics/OLAP**:
- Aggregations over large datasets
- Complex analytical queries
- Infrequent updates
- Best: Synapse Analytics, Snowflake, ClickHouse

**Blob/File Storage**:
- Large binary objects
- No query within content
- Stream/download entire object
- Best: Blob Storage, S3

---
[Back to Overview](./OVERVIEW.md)
