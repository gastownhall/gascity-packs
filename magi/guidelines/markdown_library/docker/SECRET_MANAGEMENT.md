# Secret Management

### Build-Time Secrets

Secrets in `ARG`, `ENV`, or `COPY` are prohibited — they leak into image layers. Use BuildKit secret mounts:

```dockerfile
# Build with: docker build --secret id=gh_token,src=.gh_token .
RUN --mount=type=secret,id=gh_token \
    GH_TOKEN=$(cat /run/secrets/gh_token) \
    git clone https://${GH_TOKEN}@github.com/org/private-repo.git
```

```dockerfile
RUN --mount=type=secret,id=npm_token \
    NPM_TOKEN=$(cat /run/secrets/npm_token) npm ci
```

Build with secret:
```bash
docker build --secret id=npm_token,src=.npm_token .
```

Secrets mounted this way never appear in image layers.

### Runtime Secrets

Inject secrets at runtime only.

File-based secrets via Compose:
```yaml
services:
  app:
    secrets:
      - db_password
      - api_key
    environment:
      DB_PASSWORD_FILE: /run/secrets/db_password

secrets:
  db_password:
    external: true
  api_key:
    file: ./secrets/api_key.txt
```

Environment variable injection:
```bash
docker run -e DB_PASSWORD="${DB_PASSWORD}" myapp
```

Orchestrator-managed secrets:
- Kubernetes Secrets
- Docker Swarm secrets
- HashiCorp Vault sidecars
- AWS Secrets Manager / Azure Key Vault

### Secret Rotation

Applications must support secret rotation without rebuild:
- Read secrets from files or environment at startup AND on demand.
- Reload on `SIGHUP` or poll periodically for changes.
- Never cache decrypted secrets longer than required.

---
[Back to Overview](./OVERVIEW.md)
