# LXC vs LXD

| Aspect | LXC (Proxmox-managed) | LXD |
|:-------|:----------------------|:----|
| Management | Direct config files; Proxmox-integrated | REST API; image server; clustering built-in |
| Configuration | `/etc/pve/lxc/` (Proxmox) or `/var/lib/lxc/` | Database-backed with YAML exports |
| Networking | Manual bridge config | Managed networks; OVN integration; network zones |
| Storage | Direct backend configuration | Storage pools abstraction |
| Clustering | Via Proxmox cluster or manual sync | Native clustering with distributed database |

**Recommendation:** Use Proxmox-managed LXC for infrastructure requiring tight integration with the virtualization platform. Use LXD for container-only environments requiring API-driven orchestration.

---
[Back to Overview](./OVERVIEW.md)
