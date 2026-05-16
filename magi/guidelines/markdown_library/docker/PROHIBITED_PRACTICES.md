# Prohibited Practices

### Never Do

- Use `latest` tag in production deployments; it's a moving target.
- Store secrets in images via `ENV`, `ARG`, or `COPY`.
- Run containers as root in production without explicit justification.
- Use `docker exec` for routine operations; containers are disposable.
- Modify running containers; rebuild and redeploy instead.
- Install SSH servers in containers; use `docker exec` for debugging.
- Use privileged mode without security review and explicit approval.
- Ignore health check failures; they indicate real problems.
- Write logs to files inside containers; use stdout/stderr.
- Use shell form for `ENTRYPOINT` or `CMD`; signals will not propagate.
- Include build tools in production images; use multi-stage builds.
- Use `ADD` when `COPY` suffices; `ADD` has surprising behaviors.
- Run multiple processes in one container without an init system.
- Disable security features for convenience.
- Store state in container filesystem; use volumes.
- Use container IPs directly; they change on restart.
- Commit containers to create images; use Dockerfiles.
- Perform network fetches during container runtime.
- Make implicit environment assumptions.

---
[Back to Overview](./OVERVIEW.md)
