# Compose Configuration

### File Structure

Use `compose.yaml` (modern; no `version` field). Organize multi-file configurations:

```text
project/
├── compose.yaml           # Base configuration
├── compose.override.yaml  # Development overrides (auto-loaded)
├── compose.prod.yaml      # Production overrides
└── .env                   # Environment variable defaults
```

The `version` field is deprecated in Compose v2.

### Service Definition

```yaml
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: runtime
    image: myapp/api:${VERSION:-latest}
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      - DB_HOST=db
      - LOG_LEVEL=${LOG_LEVEL:-info}
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    networks:
      - backend
    volumes:
      - app-data:/app/data
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 256M

  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER} -d ${DB_NAME}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - backend

networks:
  backend:
    driver: bridge

volumes:
  app-data:
  db-data:
```

### Profiles for Conditional Activation

```yaml
services:
  app:
    image: myapp
  debug:
    image: busybox
    profiles: ["debug"]
  test-db:
    image: postgres
    profiles: ["test"]
```

Activate with `docker compose --profile debug up`.

### Environment Management

Use `.env` files for default values; override in deployment:

```bash
docker compose up                                       # Uses .env and compose.override.yaml
docker compose -f compose.yaml -f compose.prod.yaml up  # Production
docker compose --env-file .env.prod up                  # Different env file
```

### Dependency Management

Use `depends_on` with conditions for startup ordering:

```yaml
depends_on:
  db:
    condition: service_healthy
  cache:
    condition: service_started
```

Conditions:
- `service_started`: Wait for container to start (default)
- `service_healthy`: Wait for health check to pass
- `service_completed_successfully`: Wait for container to exit successfully

---
[Back to Overview](./OVERVIEW.md)
