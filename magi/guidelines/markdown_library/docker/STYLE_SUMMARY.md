# Style Summary

| Element            | Required Style                                                                                             |
|:-------------------|:-----------------------------------------------------------------------------------------------------------|
| Base Images        | Official images; pinned to major.minor minimum (digest in production); distroless for compiled languages   |
| Dockerfile Order   | FROM → ARG → LABEL → system setup → user → WORKDIR → deps → source → build → runtime cfg → USER → HEALTHCHECK → ENTRYPOINT/CMD |
| Layer Optimization | Combine related RUN commands; clean up in same layer; order by change frequency                            |
| Multi-Stage        | Separate build and runtime stages; final stage minimal; name stages descriptively                          |
| BuildKit           | Cache mounts for package managers; `--mount=type=secret` for build-time secrets; `# syntax=docker/dockerfile:1.5` |
| Security           | Non-root user; drop capabilities; read-only filesystem; no secrets in images; `no-new-privileges:true`     |
| Scanning           | Trivy/Grype in CI blocking on HIGH/CRITICAL; SBOM generated; cosign signing for supply chain               |
| Health Checks      | Required for production images; lightweight; verify service readiness; `/health/{live,ready,startup}` split |
| Networking         | User-defined networks for multi-container apps; DNS-based service discovery; never expose database ports externally |
| Volumes            | Named volumes for data; bind mounts for config; tmpfs for sensitive temp data                              |
| Logging            | stdout/stderr only; structured JSON format; configure logging driver and rotation                          |
| Resource Limits    | Set memory and CPU limits; base on actual usage plus headroom; sized per workload type                     |
| Tags               | Semantic versions for releases; git SHA for traceability; never `latest` in production                     |
| Compose            | `compose.yaml` (no `version`); base config + override files; profiles for conditional services             |
| ENTRYPOINT/CMD     | Exec form only; ENTRYPOINT for executable; CMD for default arguments                                       |
| Build Context      | Minimize with `.dockerignore`; never include secrets or unnecessary files                                  |
| Shakedown          | Run after every runtime-surface change; isolated network; capture logs/inspect/events; classify pass/fail-blocking/fail-nonblocking/inconclusive |
| Defense in Depth   | Multi-stage + pinned digests + HEALTHCHECK + scan + non-root + resource limits + registry redundancy       |
| Rule of Three      | Build/scan + container HEALTHCHECK + orchestrator readiness probe MUST agree before production promotion   |

---

Following these rules produces Docker images that are secure, minimal, reproducible, and production-ready. The image becomes an immutable artifact that behaves identically across environments, with all variation controlled through runtime configuration and orchestration. Build once, shakedown once, deploy anywhere — with confidence.

**Apply this guidance universally to all Dockerfiles and container configurations across the organization.**

---
[Back to Overview](./OVERVIEW.md)
