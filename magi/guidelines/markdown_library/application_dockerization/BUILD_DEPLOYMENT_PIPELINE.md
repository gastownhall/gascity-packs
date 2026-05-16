# Build and Deployment Pipeline

This section covers CI/CD integration for containerized applications.

## CI/CD Integration

### Build Pipeline Stages

A complete container build pipeline includes:

1. **Restore**: Install dependencies
2. **Build**: Compile application
3. **Test**: Run unit and integration tests
4. **Publish**: Create deployment artifacts
5. **Image Build**: Create container image
6. **Image Scan**: Scan for vulnerabilities
7. **Image Push**: Push to registry
8. **Deploy**: Update running containers

### GitHub Actions Example

```yaml
name: Build and Push

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to registry
        if: github.event_name != 'pull_request'
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=sha,prefix=
            type=semver,pattern={{version}}

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### Azure DevOps Example

```yaml
trigger:
  branches:
    include:
      - main

pool:
  vmImage: 'ubuntu-latest'

variables:
  imageRepository: 'myapp'
  containerRegistry: 'myregistry.azurecr.io'
  dockerfilePath: 'Dockerfile'
  tag: '$(Build.BuildId)'

stages:
  - stage: Build
    jobs:
      - job: BuildAndPush
        steps:
          - task: Docker@2
            displayName: 'Build image'
            inputs:
              containerRegistry: 'AzureContainerRegistry'
              repository: $(imageRepository)
              command: 'build'
              Dockerfile: $(dockerfilePath)
              tags: |
                $(tag)
                latest

          - task: Docker@2
            displayName: 'Push image'
            inputs:
              containerRegistry: 'AzureContainerRegistry'
              repository: $(imageRepository)
              command: 'push'
              tags: |
                $(tag)
                latest
```

## Image Tagging Strategy

### Semantic Versioning

Use semantic versioning for release images:

```
myapp:1.0.0      # Specific version
myapp:1.0        # Latest 1.0.x
myapp:1          # Latest 1.x.x
myapp:latest     # Latest release (use with caution)
```

### Git-Based Tagging

For CI builds:

```
myapp:main-abc1234          # Branch + short SHA
myapp:pr-123                # Pull request number
myapp:20240620-abc1234      # Date + short SHA
myapp:abc1234               # Short SHA only
```

### Multi-Tag Strategy

Apply multiple tags to the same image:

```bash
docker build -t myapp:1.2.3 -t myapp:1.2 -t myapp:1 -t myapp:latest .
```

### Tag Immutability

**Production rule**: Once pushed, a specific version tag (e.g., `1.2.3`) should never be overwritten. This ensures:
- Reproducible deployments
- Reliable rollbacks
- Audit trail integrity

## Image Scanning

### Vulnerability Scanning

Scan images before deployment:

```yaml
# GitHub Actions with Trivy
- name: Scan image
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: '${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}'
    format: 'table'
    exit-code: '1'
    severity: 'CRITICAL,HIGH'
```

### Scanning in Dockerfile

Build-time scanning:

```dockerfile
# Scan stage
FROM aquasec/trivy:latest AS scanner
COPY --from=runtime /app /app
RUN trivy filesystem --exit-code 1 --severity HIGH,CRITICAL /app

# Only proceeds if scan passes
FROM runtime AS final
```

### Scanning Policies

| Severity | Action           | Justification                |
|----------|------------------|------------------------------|
| Critical | Block deployment | Active exploitation risk     |
| High     | Block deployment | Significant vulnerability    |
| Medium   | Warn, allow      | Monitor and plan remediation |
| Low      | Log only         | Track for completeness       |

## Registry Management

### Private Registry Setup

Use private registries for production images:

```bash
# Azure Container Registry
az acr create --name myregistry --resource-group mygroup --sku Standard

# AWS ECR
aws ecr create-repository --repository-name myapp

# Self-hosted (Harbor)
docker run -d -p 80:8080 goharbor/harbor-core:v2.9.0
```

### Image Lifecycle

Implement retention policies:

```bash
# Azure ACR retention policy
az acr config retention update --registry myregistry --status enabled --days 30 --type UntaggedManifests
```

### Pull Secrets

Configure pull secrets for private registries:

```yaml
# Kubernetes secret
kubectl create secret docker-registry regcred \
  --docker-server=myregistry.azurecr.io \
  --docker-username=username \
  --docker-password=password
```

---
[Back to Overview](./OVERVIEW.md)
