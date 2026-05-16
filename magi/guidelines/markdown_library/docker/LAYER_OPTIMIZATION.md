# Layer Optimization

### Layer Fundamentals

Each Dockerfile instruction that modifies the filesystem creates a layer. Layers are:
- Cached independently; unchanged layers are reused across builds.
- Stored incrementally; each layer adds to image size.
- Immutable; deleting a file in layer N does not reduce size if the file was added in layer N-1.

### Minimizing Layer Count

Combine related operations into single `RUN` instructions:

```dockerfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        gnupg \
    && curl -fsSL https://example.com/key.gpg | gpg --dearmor -o /etc/apt/keyrings/example.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/example.gpg] https://example.com/apt stable main" \
        > /etc/apt/sources.list.d/example.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends example-package \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
```

Forbidden — splitting related steps into separate layers:
```dockerfile
RUN apt-get update
RUN apt-get install -y curl
RUN rm -rf /var/lib/apt/lists/*
```

### Cache Optimization

Order instructions from least to most frequently changing:

1. Base image and system packages (change rarely)
2. Language runtime configuration
3. Dependency manifests (`package.json`, `requirements.txt`)
4. Dependency installation (changes when dependencies change)
5. Application source code (changes frequently)
6. Build commands

This ordering ensures dependency installation is cached until the manifest changes, even when source code changes every build.

### Cleanup Patterns

Remove temporary files, caches, and package manager artifacts in the same layer they're created:

- **apt**: `rm -rf /var/lib/apt/lists/*`
- **pip**: `pip install --no-cache-dir` or `rm -rf ~/.cache/pip`
- **npm**: `npm ci --omit=dev` then `npm cache clean --force`
- **apk**: `apk add --no-cache` or `rm -rf /var/cache/apk/*`

Files deleted in a subsequent layer still consume space in the image; deletion must occur in the same `RUN` instruction as creation.

### Layer Analysis

Use `docker history` to inspect layer sizes:
```bash
docker history --no-trunc --format "{{.Size}}\t{{.CreatedBy}}" myimage:latest
```

Use `dive` or similar tools for interactive layer exploration and identifying wasted space.

---
[Back to Overview](./OVERVIEW.md)
