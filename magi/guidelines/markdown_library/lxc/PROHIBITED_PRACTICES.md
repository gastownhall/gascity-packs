# Prohibited Practices

### Never Do

- Run privileged containers in production without documented security review and compensating controls.
- Create containers without explicit resource limits — defaults permit unbounded resource consumption.
- Use `latest` or unversioned template references — builds become non-reproducible.
- Store secrets in container configuration files — use external secret management.
- Bind-mount sensitive host directories (`/etc`, `/var`, `/root`) into containers.
- Disable AppArmor or seccomp to "fix" application issues without investigating root cause.
- Run containers as root when application supports non-root execution.
- Assume backups work without regular recovery testing.
- Configure HA without proper fencing — split-brain causes data corruption.
- Grant `sys_admin` capability without documented justification — it approximates full root.
- Run database containers without explicit storage configuration matching workload requirements.
- Migrate containers to nodes with incompatible network or storage configuration.
- Use linked clones for production workloads — source deletion breaks dependents.
- Expose container management interfaces to untrusted networks.
- Skip post-creation hardening because "it's just a container".
- Create containers through GUI without documenting equivalent CLI/configuration for reproducibility.

---
[Back to Overview](./OVERVIEW.md)
