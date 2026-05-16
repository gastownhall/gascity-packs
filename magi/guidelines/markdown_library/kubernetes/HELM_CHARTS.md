# Helm Charts

### Required Chart Structure

- `Chart.yaml` with accurate metadata.
- `values.yaml` with sensible defaults.
- `values.schema.json` for validation.
- `README.md` with usage documentation.
- `NOTES.txt` with post-install instructions.

### Best Practices

- Use chart dependencies for reusable components.
- Validate required values with schema.
- Use template helpers for repeated logic.

### Standard `values.yaml`

```yaml
# values.yaml
replicaCount: 3
image:
  repository: registry.example.com/app
  tag: v1.2.3
  pullPolicy: IfNotPresent
resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    cpu: 500m
    memory: 512Mi
service:
  type: ClusterIP
  port: 80
ingress:
  enabled: true
  className: nginx
  hosts:
    - host: api.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: api-tls
      hosts:
        - api.example.com
```

### Release Management

- Use semantic versioning for chart versions.
- Namespace-scoped release names.
- Test upgrades with `--dry-run`.
- Use `--atomic` for automatic rollback on failure.

---
[Back to Overview](./OVERVIEW.md)
