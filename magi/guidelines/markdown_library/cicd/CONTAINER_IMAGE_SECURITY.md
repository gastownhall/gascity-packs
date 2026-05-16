# Container Image Security

### Minimal Base Images

Use distroless, Alpine, or `scratch` (for Go/Rust). Every package in the base image is a potential vulnerability source. A full Ubuntu base carries hundreds of packages the application does not use.

### Image Scanning

Scan container images for vulnerabilities **before** publishing. Tools: Trivy, Grype, Snyk Container, registry-built-in scanning (ECR, ACR, GCR, Docker Hub). Block images with critical/high severity vulnerabilities from promotion to production. Scan both the base image layers and application dependency layers.

### Pin by SHA Digest

```dockerfile
# Wrong — mutable tag
FROM node:20-alpine

# Correct — immutable digest
FROM node:20-alpine@sha256:abc123...
```

### No Secrets in Layers

**Do not include secrets, credentials, private keys, or `.env` files in container images.** Secrets baked into image layers are extractable by anyone with access to the image. Use **multi-stage builds** to separate build-time dependencies from runtime images.

### Non-Root User

Add a `USER` directive specifying a non-root user. Configure the container runtime (Kubernetes `securityContext`, Docker `--user`) to enforce non-root execution.

### OCI Annotations

Label images with build metadata:

```dockerfile
LABEL org.opencontainers.image.source="https://github.com/org/repo"
LABEL org.opencontainers.image.revision="${COMMIT_SHA}"
LABEL org.opencontainers.image.created="${BUILD_TIMESTAMP}"
LABEL org.opencontainers.image.version="${SEMANTIC_VERSION}"
```

---
[Back to Overview](./OVERVIEW.md)
