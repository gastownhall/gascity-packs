# Style Summary

| Element | Required Configuration |
|:--------|:-----------------------|
| Privilege Mode | Unprivileged (`unprivileged: 1`) for all production containers |
| Memory | Explicit limit based on workload; no reliance on defaults |
| Swap | Set to 0 unless specifically required |
| CPU | Explicit cores and `cpulimit`; `cpuunits` for prioritization |
| cgroups | v2 unified hierarchy; `lxc.cgroup2.memory.max`, `cpu.max`, `io.max` |
| Storage | Appropriate backend for workload; explicit sizing |
| Networking | Static IP or documented DHCP; VLAN segmentation by security tier |
| Security | AppArmor enabled; seccomp profile; minimal capabilities; no unnecessary host access |
| User Namespaces | UID 0 → host UID 100000+; `lxc.idmap` for custom mappings |
| Templates | Versioned (`distro-version-purpose-vYYYY.MM.tar.zst`); stored in version control; rebuild schedule documented |
| Backups | Scheduled; PBS preferred; retention defined; recovery tested quarterly |
| HA | Requires proper fencing; shared storage; quorum maintained (3+ nodes or QDevice) |
| Migration | Offline for local storage; online requires shared storage |
| Monitoring | Host and container metrics exported; alerting configured; pve-exporter + node-exporter |
| Logging | Centralized collection; application logs to stdout/stderr; journald → Loki/ELK |
| Docker / Nesting | `features: nesting=1,keyctl=1` explicitly enabled; overlay2 driver; security implications documented |
| Boot Order | Explicit ordering matching service dependencies (1–10 infra, 11–50 backends, 51–90 apps, 91–99 edge) |
| Documentation | Purpose, owner, dependencies in container description |
| Shakedown | Real provisioning + cloud-init + network + mounts + systemd + cgroup verification; classify pass / fail-blocking / fail-nonblocking / inconclusive |
| Defense in Depth | Snapshots + offsite backups + config-as-code + monitoring + idempotent provisioning + HA + shakedown |
| Rule of Three | Snapshot + off-host backup + peer host (or 3-node cluster) — majority MUST survive any single loss |

---
[Back to Overview](./OVERVIEW.md)
