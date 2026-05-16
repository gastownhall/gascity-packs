# Development vs Production

### Development Configuration

Development images may include:
- Source code mounted via bind mount for hot reload.
- Development dependencies (nodemon, air, watchdog).
- Debug ports exposed.
- Relaxed resource constraints.
- Volume mounts for IDE integration.

```yaml
# compose.override.yaml (auto-loaded in dev)
services:
  app:
    build:
      target: development
    volumes:
      - .:/app:cached  # Source mount for hot reload
      - node_modules:/app/node_modules
    ports:
      - "8080:8080"
      - "9229:9229"  # Debug port
    environment:
      - NODE_ENV=development
      - DEBUG=*
```

### Production Configuration

Production images must have:
- Minimal base image.
- Only production dependencies; no build tools, no source code.
- Non-root user.
- Health checks defined.
- Read-only root filesystem where possible.
- Resource limits set.
- Logging to stdout/stderr.

Production must NOT have:
- Source code (only compiled artifacts).
- Development dependencies.
- Debug ports exposed.

### Configuration Layering

Use Compose override files for environment-specific configuration:

```bash
# Development (auto-loads override)
docker compose up

# Production
docker compose -f compose.yaml -f compose.prod.yaml up -d
```

Keep base `compose.yaml` environment-agnostic; layer environment specifics via override files.

---
[Back to Overview](./OVERVIEW.md)
