# Core Principles

These guidelines define strict, secure, and operationally sound patterns for LXC container deployment and management, with emphasis on Proxmox VE environments. The standards optimize for:

- **Isolation Without Overhead**: LXC provides OS-level virtualization sharing the host kernel; workloads run with near-native performance while maintaining logical separation between tenants.
- **Security by Default**: Unprivileged containers, AppArmor profiles, and capability restrictions are baseline requirements — not optional hardening applied after incidents.
- **Resource Determinism**: Every container has explicit CPU, memory, and I/O constraints preventing noisy neighbor effects and enabling capacity planning.
- **Operational Predictability**: Container configurations are declarative, version-controlled, and reproducible across environments without manual intervention.
- **Infrastructure as Code**: Proxmox configurations, templates, and provisioning scripts exist in source control; no container exists that cannot be rebuilt from documented specifications.

### Primary Rule: Unprivileged Containers Are Non-Negotiable

Privileged containers run with root inside the container mapping to root on the host. A container escape in a privileged container grants full host access. Unprivileged containers use user namespace mapping where container root maps to an unprivileged UID on the host. **Every production container runs unprivileged unless a documented, reviewed exception exists with compensating controls.**

```ini
unprivileged: 1
```

### Secondary Rule: Explicit Resource Boundaries

Containers without resource limits consume unbounded host resources. A single runaway process causes cascading failures across all co-located workloads. Every container specifies CPU cores or shares, memory limits with swap controls, and I/O bandwidth constraints. Defaults are not acceptable; explicit allocation based on workload characterization is mandatory.

### Proxmox Context

Proxmox VE manages LXC containers through the `pct` command-line tool and web interface. Container configurations persist in `/etc/pve/lxc/<vmid>.conf`. The cluster filesystem (`pmxcfs`) synchronizes configurations across nodes. These guidelines assume Proxmox VE 8.x or later; earlier versions may lack features referenced here.

### LXC vs Docker/Podman

LXC containers are **system containers** — they run a full init system and behave like lightweight virtual machines. Docker and Podman are application containers optimized for single-process workloads.

Use LXC when you need:

- Multiple services within one container.
- Traditional system administration patterns.
- Long-lived infrastructure components (DNS, monitoring, databases).
- Workloads requiring systemd or complex init sequences.

Use Docker/Podman when you need:

- Immutable application deployments.
- Microservice architectures.
- CI/CD pipeline artifacts.
- Rapid horizontal scaling of stateless services.

---
[Back to Overview](./OVERVIEW.md)
