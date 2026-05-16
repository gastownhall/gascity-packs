# Proxmox Integration

### `pct` Command Patterns

| Command | Description | Required Options |
|:--------|:------------|:-----------------|
| `pct create <vmid> <template>` | Create container | `--hostname`, `--memory`, `--cores`, `--rootfs`, `--unprivileged` |
| `pct set <vmid>` | Modify configuration | — |
| `pct migrate <vmid> <target>` | Move between nodes | `[--online]` |

### Cluster Filesystem (`pmxcfs`)

Configuration synchronization across cluster nodes — backed by FUSE-mounted distributed database. Key paths:

- `/etc/pve/lxc/`
- `/etc/pve/storage.cfg`
- `/etc/pve/datacenter.cfg`

### API Integration

```bash
# API access for automation
pvesh get /nodes/{node}/lxc
pvesh create /nodes/{node}/lxc --vmid 101 --ostemplate local:vztmpl/debian-12.tar.zst
pvesh set /nodes/{node}/lxc/{vmid}/config
```

---
[Back to Overview](./OVERVIEW.md)
