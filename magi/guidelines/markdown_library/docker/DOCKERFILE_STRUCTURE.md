# Dockerfile Structure and Syntax

### Instruction Ordering

Order Dockerfile instructions to maximize layer cache efficiency:

1. `FROM` with explicit tag or digest
2. `ARG` for build-time variables needed early
3. `LABEL` for metadata
4. System package installation
5. User creation
6. `WORKDIR` establishment
7. Dependency file copy (`package.json`, `requirements.txt`, `go.mod`)
8. Dependency installation
9. Application source copy
10. Build commands
11. Runtime configuration (`ENV`, `EXPOSE`, `VOLUME`)
12. `USER` switch to non-root
13. `HEALTHCHECK` definition
14. `ENTRYPOINT` and `CMD`

### Instruction Syntax Standards

**FROM**: Always specify a tag; never use implicit `latest`:
```dockerfile
FROM python:3.14-slim AS builder
```

**LABEL**: Include standard metadata for image discovery and management:
```dockerfile
LABEL org.opencontainers.image.source="https://github.com/org/repo" \
      org.opencontainers.image.version="1.2.3" \
      org.opencontainers.image.description="Service description"
```

**RUN**: Combine related commands to reduce layers; clean up in the same layer:
```dockerfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
```

**COPY**: Prefer `COPY` over `ADD`; use `ADD` only for automatic archive extraction or remote URLs (rare):
```dockerfile
COPY --chown=app:app requirements.txt .
COPY --from=builder /app/dist /app
```

**ENV**: Set runtime environment variables; avoid secrets:
```dockerfile
ENV APP_HOME=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
```

**WORKDIR**: Always use absolute paths; create implicitly:
```dockerfile
WORKDIR /app
```

**USER**: Switch to non-root before final instructions:
```dockerfile
RUN addgroup --system --gid 1001 app \
    && adduser --system --uid 1001 --gid 1001 app
USER app
```

**EXPOSE**: Document expected ports; does not publish ports:
```dockerfile
EXPOSE 8080
```

**ENTRYPOINT** and **CMD**: Use exec form (JSON array) to ensure proper signal handling:
```dockerfile
ENTRYPOINT ["python", "-m", "uvicorn"]
CMD ["main:app", "--host", "0.0.0.0", "--port", "8080"]
```

Forbidden — shell form breaks signal propagation:
```dockerfile
ENTRYPOINT python -m myapp
```

### Shell Form vs Exec Form

- **Exec form** `["executable", "arg1", "arg2"]`: Runs directly without shell; receives signals properly; required for production.
- **Shell form** `executable arg1 arg2`: Wraps in `/bin/sh -c`; enables variable expansion but breaks signal handling.

Use exec form for `ENTRYPOINT`, `CMD`, and any `RUN` instruction that must handle signals or where shell features are unnecessary.

### COPY vs ADD

Prefer `COPY` over `ADD`. Use `ADD` only when automatic tarball extraction or HTTP URL fetch is genuinely required.

```dockerfile
COPY --chown=app:app ./src /app
```

---
[Back to Overview](./OVERVIEW.md)
