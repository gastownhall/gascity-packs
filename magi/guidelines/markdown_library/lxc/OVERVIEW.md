# LXC Container Library

These guidelines define strict, secure, and operationally sound patterns for LXC container deployment and management, with emphasis on Proxmox VE environments.

## Critical Mandates (Read First)
- **Unprivileged Containers Are Non-Negotiable** — `unprivileged: 1` for every production container.
- **Explicit Resource Boundaries** — every container specifies memory, swap, cores, `cpulimit`, and I/O constraints.
- **Infrastructure as Code** — Proxmox configurations and provisioning scripts in source control.
- **Snapshots + Off-host Backups + Peer Host** — minimum recovery triad.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [Container vs Virtual Machine Selection](./CONTAINER_VS_VM.md)
3. [LXC vs LXD](./LXC_VS_LXD.md)
4. [Template Management](./TEMPLATE_MANAGEMENT.md)
5. [Proxmox Integration](./PROXMOX_INTEGRATION.md)
6. [Container Creation and Configuration](./CONTAINER_CREATION.md)
7. [Resource Allocation](./RESOURCE_ALLOCATION.md)
8. [Storage Backend Selection](./STORAGE_BACKENDS.md)
9. [Networking Configuration](./NETWORKING.md)
10. [Security Hardening](./SECURITY_HARDENING.md)
11. [Filesystem and Mount Configuration](./FILESYSTEM_MOUNTS.md)
12. [Backup and Disaster Recovery](./BACKUP_RECOVERY.md)
13. [Migration and High Availability](./MIGRATION_HA.md)
14. [Lifecycle Management](./LIFECYCLE.md)
15. [Monitoring and Observability](./MONITORING.md)
16. [Nested Virtualization and Docker Integration](./NESTED_DOCKER.md)
17. [Cluster Operations](./CLUSTER_OPERATIONS.md)
18. [Troubleshooting Patterns](./TROUBLESHOOTING.md)
19. [Automation Templates](./AUTOMATION_TEMPLATES.md)
20. [Shakedown — Post-Provision Validation](./SHAKEDOWN.md)
21. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
22. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
23. [Required Practices](./REQUIRED_PRACTICES.md)
24. [Style Summary](./STYLE_SUMMARY.md)
