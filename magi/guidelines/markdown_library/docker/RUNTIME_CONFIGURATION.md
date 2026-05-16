# Runtime Configuration

### Environment Variables

Use environment variables for runtime configuration that varies between environments:

```dockerfile
ENV APP_PORT=8080 \
    LOG_LEVEL=info \
    DB_POOL_SIZE=10
```

Override at runtime:
```bash
docker run -e LOG_LEVEL=debug -e DB_HOST=prod-db.internal myimage
```

Forbidden — environment-specific defaults baked in:
```dockerfile
ENV DATABASE_HOST=prod-db.example.com
```

Correct — empty default, overridden at runtime:
```dockerfile
ENV DATABASE_HOST=""
```

### Configuration File Mounting

For complex configuration, mount files at runtime rather than baking into images:

```bash
docker run -v ./config/app.yaml:/app/config/app.yaml:ro myimage
```

Mark configuration mounts as read-only (`:ro`) to prevent accidental modification.

### ENTRYPOINT vs CMD

- **ENTRYPOINT**: The executable; rarely overridden; defines what the container *is*.
- **CMD**: Default arguments to entrypoint; easily overridden; defines default behavior.

Pattern for flexibility:
```dockerfile
ENTRYPOINT ["python", "-m", "myapp"]
CMD ["serve", "--port", "8080"]
```

Override CMD at runtime:
```bash
docker run myimage migrate --target latest
```

### Signal Handling

Containers receive signals for graceful shutdown. The process running as PID 1 must:
- Handle SIGTERM for graceful shutdown.
- Propagate signals to child processes if running a supervisor.
- Exit with appropriate code (0 for success, non-zero for failure).

Use exec form for ENTRYPOINT to ensure the application receives signals directly. Shell form wraps in `sh -c` which may not propagate signals correctly.

### Init Process

For applications that spawn child processes, use an init system to reap zombies and forward signals:

```bash
docker run --init myimage
```

Or include tini in the image:
```dockerfile
RUN apk add --no-cache tini
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["myapp"]
```

---
[Back to Overview](./OVERVIEW.md)
