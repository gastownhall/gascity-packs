# Required Practices

### Always Do

- Pin base image versions to at least major.minor.
- Use multi-stage builds to separate build and runtime dependencies.
- Run as non-root user in production.
- Define health checks for orchestration integration.
- Use `.dockerignore` to minimize build context.
- Set resource limits to prevent runaway containers.
- Scan images for vulnerabilities in CI pipeline.
- Use exec form for `ENTRYPOINT` and `CMD`.
- Log to stdout/stderr in structured format.
- Clean up temporary files in the same layer they are created.
- Use named volumes for persistent data.
- Document exposed ports with `EXPOSE`.
- Apply labels for image metadata and discovery.
- Test images locally before pushing to registry.
- Implement graceful shutdown handling.
- Use BuildKit for advanced features (cache mounts, secrets).
- Externalize all configuration.
- Handle signals properly via exec-form entrypoint or init process.
- Implement proper application-level error handling.
- Run a container shakedown after every build that touches the runtime surface.

---
[Back to Overview](./OVERVIEW.md)
