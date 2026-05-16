# Container Composition

This section covers composing multiple containers and managing dependencies.

## Docker Compose for Development

### Development Compose File

```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8080:8080"
    environment:
      - ASPNETCORE_ENVIRONMENT=Development
      - ConnectionStrings__DefaultConnection=Host=postgres;Database=appdb;Username=dev;Password=devpass
      - ConnectionStrings__Redis=redis:6379
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./logs:/app/logs

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: devpass
      POSTGRES_DB: appdb
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./db/init:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U dev -d appdb"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

### Multi-Service Application

```yaml
version: '3.8'

services:
  # API Gateway
  gateway:
    build:
      context: ./src/Gateway
    ports:
      - "8080:8080"
    environment:
      - ASPNETCORE_ENVIRONMENT=Development
      - OrderService__Url=http://order-api:8080
      - ProductService__Url=http://product-api:8080
    depends_on:
      - order-api
      - product-api

  # Order Service
  order-api:
    build:
      context: ./src/OrderService
    environment:
      - ASPNETCORE_ENVIRONMENT=Development
      - ConnectionStrings__Database=Host=postgres;Database=orders;Username=dev;Password=devpass
      - RabbitMQ__Host=rabbitmq
    depends_on:
      postgres:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy

  # Product Service
  product-api:
    build:
      context: ./src/ProductService
    environment:
      - ASPNETCORE_ENVIRONMENT=Development
      - ConnectionStrings__Database=Host=postgres;Database=products;Username=dev;Password=devpass
      - Redis__Connection=redis:6379
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  # Order Worker
  order-worker:
    build:
      context: ./src/OrderWorker
    environment:
      - ConnectionStrings__Database=Host=postgres;Database=orders;Username=dev;Password=devpass
      - RabbitMQ__Host=rabbitmq
    depends_on:
      - rabbitmq
      - postgres

  # Infrastructure
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: devpass
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./db/init:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U dev"]
      interval: 5s
      timeout: 5s
      retries: 5

  rabbitmq:
    image: rabbitmq:3.12-management-alpine
    ports:
      - "15672:15672"
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "check_running"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

### Development Overrides

Use compose overrides for development-specific settings:

```yaml
# docker-compose.override.yml (automatically merged)
version: '3.8'

services:
  app:
    build:
      target: build  # Stop at build stage for debugging
    volumes:
      - .:/src  # Mount source for hot reload
    environment:
      - DOTNET_USE_POLLING_FILE_WATCHER=1  # Hot reload in container
```

## Dependency Management

### Service Startup Order

Use `depends_on` with health checks for proper ordering:

```yaml
services:
  app:
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
```

### Application-Level Retry

Don't rely solely on compose ordering. Implement connection retry in the application:

```csharp
builder.Services.AddDbContext<AppDbContext>(options =>
{
    options.UseNpgsql(connectionString, npgsqlOptions =>
    {
        npgsqlOptions.EnableRetryOnFailure(
            maxRetryCount: 10,
            maxRetryDelay: TimeSpan.FromSeconds(30),
            errorCodesToAdd: null);
    });
});
```

### Wait-for-It Pattern

For complex startup scenarios, use a wait script:

```dockerfile
# Install wait-for-it
RUN apt-get update && apt-get install -y wait-for-it && rm -rf /var/lib/apt/lists/*

# Wait for dependencies before starting
CMD ["wait-for-it", "postgres:5432", "--timeout=60", "--", "dotnet", "MyApp.dll"]
```

## Network Configuration

### Container Networking

Docker Compose creates a default network where services resolve by name:

```csharp
// Service discovery by container name
var connectionString = "Host=postgres;Database=app;Username=user;Password=pass;";
var redisConnection = "redis:6379";
var rabbitConnection = "amqp://user:pass@rabbitmq:5672";
```

### External Network Access

For services that need external access:

```yaml
services:
  app:
    ports:
      - "8080:8080"  # Map container port to host

  postgres:
    ports:
      - "5432:5432"  # Only expose in development
```

### Network Isolation

Create explicit networks for service isolation:

```yaml
version: '3.8'

services:
  frontend:
    networks:
      - frontend-net

  backend:
    networks:
      - frontend-net
      - backend-net

  database:
    networks:
      - backend-net

networks:
  frontend-net:
  backend-net:
```

---
[Back to Overview](./OVERVIEW.md)
