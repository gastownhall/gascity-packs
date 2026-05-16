# Registry and Distribution

### Image Tagging Strategy

- **latest**: Avoid for production; use for development convenience only.
- **Semantic versions**: `1.2.3`, `1.2`, `1` for release tracking.
- **Git SHA**: `sha-abc123def`, `main-abc123def` for exact commit traceability.
- **Environment**: `prod`, `staging` for deployment-specific builds (mutable).

Tag images with multiple tags for flexibility:
```bash
docker tag myapp:latest myapp:1.2.3
docker tag myapp:latest myapp:1.2
docker tag myapp:latest myapp:abc123def
```

### Registry Authentication

```bash
docker login registry.example.com
echo "$REGISTRY_PASSWORD" | docker login -u "$REGISTRY_USER" --password-stdin registry.example.com
```

For CI pipelines, use service account tokens or registry-specific authentication mechanisms.

### Push and Pull Patterns

```bash
docker push registry.example.com/myapp:1.2.3
docker pull registry.example.com/myapp:1.2.3
```

Use registry mirrors for:
- Air-gapped environments
- Reducing external network dependency
- Caching frequently used base images

### Image Retention

- Implement retention policies in your registry.
- Delete untagged images (dangling manifests) regularly.
- Retain production-deployed versions for rollback capability.
- Archive images beyond retention window if audit requirements demand.

---
[Back to Overview](./OVERVIEW.md)
