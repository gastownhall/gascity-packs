# Containerization Assessment

Before writing a single Dockerfile, assess the application's container-readiness and identify required changes. Rushing to containerize without assessment produces containers that don't work in production.

## Application Architecture Analysis

### Statefulness Assessment

Containers are fundamentally stateless. Identify all state the application maintains:

**Filesystem State**:
- Log files written to disk
- Temporary files during processing
- Uploaded files stored locally
- Cache files on the filesystem
- Configuration files modified at runtime

**Memory State**:
- In-process caches
- Session storage
- Connection pools
- Background job queues
- Rate limiting counters

**External State Dependencies**:
- Database connections requiring specific host identity
- Message queue subscriptions tied to hostname
- File shares mounted at specific paths
- Network storage with host-specific credentials

For each state type, determine:
1. Is this state essential or incidental?
2. Can this state be externalized?
3. What happens if this state is lost?
4. How does this affect horizontal scaling?

### State Externalization Strategy

| State Type      | Externalization Target                | Implementation                         |
|-----------------|---------------------------------------|----------------------------------------|
| Session storage | Redis, database                       | Replace in-memory with distributed     |
| File uploads    | Blob storage (S3, Azure Blob)         | Store externally, keep reference in DB |
| Logs            | stdout/stderr                         | Write to streams, not files            |
| Caches          | Redis, Memcached                      | Replace in-process with distributed    |
| Temp files      | Container tmpfs or short-lived volume | Accept loss on restart                 |
| Config changes  | Environment variables, config service | Restart to apply changes               |

### Dependency Inventory

Document every external dependency the application requires:

**Runtime Dependencies**:
- Language runtime version and variant
- Native libraries (.so, .dll files)
- System packages (openssl, ca-certificates, tzdata)
- Fonts (for image/PDF generation)
- External binaries (imagemagick, ffmpeg, wkhtmltopdf)

**Network Dependencies**:
- Database connections (host, port, protocol)
- Cache connections
- Message queue connections
- External API endpoints
- Service discovery mechanisms
- DNS resolution requirements

**Filesystem Dependencies**:
- Configuration file locations
- Certificate/key file paths
- Static asset directories
- Writable directories (uploads, temp, logs)

**Environment Dependencies**:
- Required environment variables
- Optional environment variables with defaults
- Environment variables with secrets

### Startup and Shutdown Analysis

Document the application's lifecycle requirements:

**Startup Sequence**:
- How long does the application take to start?
- What initialization occurs before accepting requests?
- Are there database migrations or schema checks?
- Does the application verify external dependencies on startup?
- What happens if dependencies are unavailable at startup?

**Readiness Criteria**:
- When is the application ready to receive traffic?
- Is there a warm-up period after startup?
- Are there background tasks that must complete first?

**Shutdown Sequence**:
- Does the application handle SIGTERM?
- How long does graceful shutdown take?
- Are in-flight requests completed or dropped?
- Are background jobs checkpointed or abandoned?
- Are connections properly closed?

### Network Model Assessment

Understand how the application uses networking:

**Listening Ports**:
- What ports does the application bind to?
- Are ports configurable or hardcoded?
- Does the application bind to specific interfaces or all interfaces?

**Outbound Connections**:
- What external services does the application connect to?
- Are connection strings configurable?
- Does the application use hostname resolution or IP addresses?
- Are there long-lived connections that need keep-alives?

**Service Discovery**:
- How does the application find dependent services?
- Are service locations hardcoded, configured, or discovered?
- Does the application cache DNS lookups?

## Component Isolation Analysis

Not every part of an application should be in the same container. Analyze which components should be isolated.

### Isolation Candidates

Identify components that are candidates for separate containers:

**Different Scaling Requirements**:
- Web frontends vs background workers
- API servers vs batch processors
- High-throughput services vs low-latency services

**Different Lifecycle Requirements**:
- Components with different release cadences
- Components with different uptime requirements
- Components with different security requirements

**Different Resource Profiles**:
- CPU-intensive vs memory-intensive
- Network-intensive vs disk-intensive
- Bursty vs steady workloads

**Different Technology Stacks**:
- Legacy components requiring older runtimes
- Components written in different languages
- Components with conflicting dependencies

### Isolation Decision Framework

```
Should this component be in a separate container?
├── Does it scale independently from the main application?
│   ├── Yes → Separate container
│   └── No → Continue evaluation
├── Does it have a different release cadence?
│   ├── Yes → Separate container
│   └── No → Continue evaluation
├── Does it have conflicting dependencies?
│   ├── Yes → Separate container
│   └── No → Continue evaluation
├── Does it require different resource limits?
│   ├── Yes → Separate container
│   └── No → Continue evaluation
├── Is it a cross-cutting concern (logging, metrics, auth proxy)?
│   ├── Yes → Consider sidecar pattern
│   └── No → Keep in main container
```

### Component Communication Patterns

When isolating components, define communication patterns:

**Synchronous Communication**:
- HTTP/gRPC between containers
- Service mesh for traffic management
- Load balancer for distribution

**Asynchronous Communication**:
- Message queues (RabbitMQ, Azure Service Bus)
- Event streaming (Kafka, Event Hubs)
- Pub/sub patterns

**Shared State**:
- External database (not container-local)
- Distributed cache
- Object storage for large data

### Anti-Pattern: Shared Volumes Between Containers

Do not use shared volumes for container-to-container communication:

```
# PROHIBITED: Shared volume for IPC
Container A writes to /shared/data.json
Container B reads from /shared/data.json
```

Problems:
- No delivery guarantees
- Race conditions on read/write
- File locking issues
- Breaks when containers run on different nodes

Correct approach: Use explicit communication channels (HTTP, message queues, databases).

## Database Containerization Decisions

Databases require careful consideration for containerization.

### When to Containerize Databases

**Containerize for Development**:
- Local development environments
- CI/CD pipeline testing
- Ephemeral review environments
- Integration testing

**Do Not Containerize for Production** (typically):
- Primary transactional databases
- Databases requiring durability guarantees
- Databases with complex replication
- Databases exceeding single-node capacity

### Database Container Trade-offs

| Consideration          | Containerized                | Managed Service          |
|------------------------|------------------------------|--------------------------|
| **Operational burden** | High (you manage everything) | Low (provider manages)   |
| **Data durability**    | Complex (volume management)  | Built-in                 |
| **Performance tuning** | Manual                       | Often automatic          |
| **Backup/restore**     | Manual implementation        | Built-in                 |
| **High availability**  | Complex to implement         | Built-in                 |
| **Cost**               | Lower at small scale         | Lower at scale (TCO)     |
| **Portability**        | High                         | Vendor-specific          |
| **Dev/prod parity**    | Excellent                    | Often different versions |

### Development Database Containers

For development and testing, containerized databases provide consistency:

```yaml
# Example: Development PostgreSQL
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: devuser
      POSTGRES_PASSWORD: devpassword
      POSTGRES_DB: appdb
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-scripts:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U devuser -d appdb"]
      interval: 5s
      timeout: 5s
      retries: 5
```

Key patterns:
- Use named volumes for data persistence across container restarts
- Use init scripts for schema/seed data
- Match production version as closely as possible
- Include health checks for dependency orchestration

## Message Queue and Cache Containerization

### Message Queues

**Development**: Containerize for local testing and CI/CD.

```yaml
# Example: Development RabbitMQ
services:
  rabbitmq:
    image: rabbitmq:3.12-management-alpine
    environment:
      RABBITMQ_DEFAULT_USER: devuser
      RABBITMQ_DEFAULT_PASS: devpassword
    ports:
      - "5672:5672"
      - "15672:15672"
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "check_running"]
      interval: 10s
      timeout: 5s
      retries: 5
```

**Production**: Use managed services (Azure Service Bus, Amazon SQS, CloudAMQP) unless you have dedicated queue infrastructure expertise.

### Caches

**Redis for development**:

```yaml
services:
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5
```

**Production considerations**:
- In-memory caches (Redis, Memcached) are more amenable to containerization than databases
- Data loss on restart is often acceptable for caches
- Consider managed services for clustering and high availability

---
[Back to Overview](./OVERVIEW.md)
