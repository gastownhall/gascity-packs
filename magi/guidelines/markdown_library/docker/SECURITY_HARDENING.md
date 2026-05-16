# Security Hardening

### Non-Root Execution

Run containers as non-root users. Create a dedicated user in the Dockerfile:

```dockerfile
RUN addgroup --system --gid 1001 app \
    && adduser --system --uid 1001 --gid 1001 --no-create-home app
USER app
```

For distroless images, use the built-in nonroot user:
```dockerfile
FROM gcr.io/distroless/static:nonroot
USER nonroot:nonroot
```

Running as UID 0 in production is prohibited.

### Filesystem Permissions

- Application files owned by root, readable by app user
- Writable directories (temp, cache, data) owned by app user
- No world-writable directories except explicit tmpfs mounts

```dockerfile
COPY --chown=root:root --chmod=755 ./app /app
RUN mkdir -p /app/data && chown app:app /app/data
```

### Read-Only Root Filesystem

Run containers with read-only root filesystem; mount tmpfs for writable paths:

```bash
docker run --read-only --tmpfs /tmp:rw,noexec,nosuid myimage
```

In Compose:
```yaml
services:
  app:
    read_only: true
    tmpfs:
      - /tmp
      - /var/run
    volumes:
      - app-data:/app/data
```

### Capability Dropping

Drop all capabilities and add back only what's required:

```bash
docker run --cap-drop=ALL --cap-add=NET_BIND_SERVICE myimage
```

In Compose:
```yaml
services:
  app:
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE  # Only if binding to ports < 1024
```

Most applications need no capabilities. Web servers binding to ports below 1024 need `NET_BIND_SERVICE`; prefer binding to high ports and mapping externally.

### Security Options

```yaml
services:
  app:
    security_opt:
      - no-new-privileges:true
      - seccomp:unconfined  # Only if needed
      - apparmor:docker-default
```

`no-new-privileges:true` prevents privilege escalation via setuid binaries.

### No Secrets in Images

Secrets never appear in:
- Environment variables set via `ENV`
- Files copied into the image
- Build arguments (`ARG`) for sensitive values
- Layer history

Use runtime secret injection (see Section 10).

---
[Back to Overview](./OVERVIEW.md)
