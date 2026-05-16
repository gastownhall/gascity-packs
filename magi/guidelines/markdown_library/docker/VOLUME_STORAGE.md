# Volume and Storage Management

### Volume Types

- **Named volumes**: Managed by Docker; persist beyond container lifecycle; recommended for data persistence.
- **Bind mounts**: Map host path to container path; useful for development and configuration.
- **tmpfs mounts**: In-memory storage; never written to disk; use for sensitive temporary data.

### Named Volumes

```bash
docker volume create app-data
docker run -v app-data:/app/data myimage
```

In Compose:
```yaml
volumes:
  app-data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /data/app

services:
  app:
    volumes:
      - app-data:/app/data
```

### Bind Mounts

```bash
docker run -v /host/path:/container/path:ro myimage
docker run -v $(pwd)/config:/app/config:ro myimage
```

Bind mount options:
- `:ro` — Read-only
- `:rw` — Read-write (default)
- `:cached` — Host-authoritative (macOS performance)
- `:delegated` — Container-authoritative (macOS performance)

### tmpfs Mounts

```yaml
services:
  app:
    tmpfs:
      - /tmp
      - /run:size=10M,mode=0770,uid=1000,gid=1000
```

### Volume Permissions

Volume data is created with root ownership by default. The non-root user must own writable directories:

```dockerfile
RUN mkdir -p /app/data && chown -R app:app /app/data
VOLUME /app/data
USER app
```

Alternatively, use an entrypoint script to fix permissions at runtime when running as root initially, then dropping privileges.

### Backup and Persistence

Back up named volumes regularly:
```bash
docker run --rm \
    -v myapp_data:/source:ro \
    -v ./backups:/backup \
    alpine tar czf /backup/data-$(date +%Y%m%d).tar.gz -C /source .
```

- Document which volumes contain critical data.
- Never store application state in the container's writable layer; it's lost on container removal.

---
[Back to Overview](./OVERVIEW.md)
