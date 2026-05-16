# Anti-Patterns to Avoid

### Using the Wrong Tool

| Anti-Pattern                         | Problem                                     | Solution             |
|--------------------------------------|---------------------------------------------|----------------------|
| SQL for session storage              | Schema overhead, connection pool exhaustion | Redis with TTL       |
| Redis as primary database            | Data loss risk, no complex queries          | SQL or Cosmos DB     |
| Cosmos DB for simple CRUD            | Cost, complexity overkill                   | SQL Database         |
| Blob Storage for small records       | High latency, no querying                   | Table Storage or SQL |
| In-process cache for shared state    | Inconsistency across instances              | Redis                |
| Storage Queues for complex workflows | Missing features (DLQ, scheduling)          | Service Bus          |
| RabbitMQ for log streaming           | Not designed for replay, log retention      | Kafka or Event Hubs  |

### Ignoring Operational Complexity

Every technology added requires:
- Monitoring and alerting setup
- Backup and recovery procedures
- Security configuration
- Team expertise
- On-call runbooks

A three-technology architecture that the team understands deeply is better than a seven-technology architecture with shallow knowledge.

### Premature Optimization

- Don't add Redis "for performance" without measuring the problem
- Don't use Cosmos DB "for scale" when SQL handles the load fine
- Don't add message queues without async requirements
- Measure first, optimize second

### Ignoring Cost

Monthly cost of different storage options for 1TB data (approximate, varies by region and usage):

| Service             | Hot/Active | Notes                         |
|---------------------|------------|-------------------------------|
| Blob Storage (Hot)  | ~$20       | Plus access costs             |
| Blob Storage (Cool) | ~$10       | Higher access costs           |
| SQL Database (GP)   | ~$500-2000 | Depending on DTU/vCore        |
| Cosmos DB           | ~$500-5000 | Depending on RU/s provisioned |
| Redis (Premium)     | ~$500-2000 | Depending on tier and size    |

Don't use expensive services for cold data. Tier your storage.

---
[Back to Overview](./OVERVIEW.md)
