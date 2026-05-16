# Base Image Selection

### Selection Criteria

The base image determines the foundation for security updates, available packages, and image size. Choose deliberately:

- **Official images** from Docker Hub or verified publishers for common runtimes
- **Distroless images** for compiled languages where no shell or package manager is needed
- **Alpine variants** when a shell is required but size must remain minimal
- **Debian/Ubuntu slim variants** when glibc compatibility or specific packages are required
- **Scratch** for statically compiled binaries with zero dependencies

### Image Provenance

- Pull from trusted registries only; configure registry mirrors for air-gapped environments
- Pin images by digest for reproducibility: `python:3.14-slim@sha256:abc123...`
- Tag-based references (`python:3.14`) are acceptable for development but introduce drift risk in production
- Verify image signatures when available; reject unsigned images in security-sensitive contexts

### Base Image Hierarchy

| Use Case          | Recommended Base                                                                | Size Range | Notes                                   |
|:------------------|:--------------------------------------------------------------------------------|:-----------|:----------------------------------------|
| Go, Rust (static) | `scratch` or `gcr.io/distroless/static`                                         | 0–20 MB    | Zero attack surface                     |
| Java              | `eclipse-temurin:21-jre-alpine` or `gcr.io/distroless/java21:nonroot`           | 100–200 MB | JRE only, no JDK                        |
| Python            | `python:3.14-slim` or `gcr.io/distroless/python3:nonroot`                       | 120–150 MB | Avoid full `python:3.14`                |
| Node.js           | `node:20-alpine` or `gcr.io/distroless/nodejs20:latest`                         | 50–80 MB   | Alpine for size; slim for compatibility |
| .NET              | `mcr.microsoft.com/dotnet/runtime:8.0-alpine` or `…runtime:8.0-chiseled`        | 80–100 MB  | Runtime only, not SDK                   |
| General Linux     | `debian:bookworm-slim` or `ubuntu:24.04`                                        | 70–100 MB  | When specific packages needed           |

### Distroless Preference for Compiled Languages

| Language | Recommended Image |
|:---------|:------------------|
| Java | `gcr.io/distroless/java21:nonroot` |
| Node.js | `gcr.io/distroless/nodejs20:latest` |
| Python | `gcr.io/distroless/python3:nonroot` |
| .NET | `mcr.microsoft.com/dotnet/runtime:8.0-chiseled` |
| Go/Rust static | `gcr.io/distroless/static:nonroot` |

Distroless images contain no shell, no package manager, and no busybox — only the application and its runtime dependencies.

### Version Pinning Strategy

- Pin major.minor version minimum: `python:3.14`, not `python:3` or `python:latest`.
- Pin digest for production builds requiring absolute reproducibility:
  ```dockerfile
  FROM python:3.14-slim@sha256:abc123...
  ```
- Forbidden:
  ```dockerfile
  FROM python:latest
  ```
- Document upgrade cadence; base images require regular updates for security patches.
- Automate base image vulnerability scanning in CI pipelines.

---
[Back to Overview](./OVERVIEW.md)
