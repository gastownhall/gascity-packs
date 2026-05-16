# Container Creation and Configuration

### Container Identification

- **VMID**: unique numeric identifier within the cluster.
- **Hostname**: descriptive, DNS-compliant name reflecting the container's purpose.
- **Description**: document purpose, owner, and dependencies in the notes field.

Numbering conventions:

| Range | Use |
|:------|:----|
| 100–199 | Infrastructure services (DNS, DHCP, monitoring) |
| 200–299 | Development environments |
| 300–399 | Staging / QA |
| 400–499 | Production services |
| 900–999 | Templates and temporary containers |

### CLI Creation with Explicit Parameters

```bash
pct create 101 local:vztmpl/debian-12-standard_12.2-1_amd64.tar.zst \
    --hostname dns-primary \
    --memory 1024 \
    --swap 0 \
    --cores 2 \
    --cpulimit 1 \
    --rootfs local-lvm:8 \
    --net0 name=eth0,bridge=vmbr0,ip=10.0.0.10/24,gw=10.0.0.1 \
    --nameserver 1.1.1.1 \
    --searchdomain internal.example.com \
    --unprivileged 1 \
    --features nesting=0 \
    --onboot 1 \
    --startup order=1,up=30,down=60 \
    --protection 0 \
    --password \
    --ssh-public-keys /root/.ssh/authorized_keys
```

Container configurations reside in `/etc/pve/lxc/<vmid>.conf`. Direct editing is supported but changes require container restart for most parameters.

### Essential Configuration Parameters

Every container configuration must explicitly specify:

| Parameter | Purpose | Requirement |
|:----------|:--------|:------------|
| `memory` | RAM allocation in MB | Explicit limit based on workload |
| `swap` | Swap allocation in MB | Set to 0 unless specifically needed |
| `cores` | CPU core count | Explicit allocation |
| `cpulimit` | CPU usage ceiling | Prevent single container from monopolizing |
| `rootfs` | Root filesystem storage and size | Appropriate storage backend and size |
| `net0` | Network interface configuration | Static IP or documented DHCP reservation |
| `unprivileged` | Container privilege mode | Always 1 unless documented exception |
| `onboot` | Auto-start behavior | Explicit yes/no based on criticality |
| `startup` | Boot order and delays | Defined for dependency management |

### Post-Creation Configuration

- Configure timezone: `timedatectl set-timezone UTC`.
- Configure locale if non-default required.
- Update package lists and apply security updates.
- Install baseline monitoring agents.
- Configure centralized logging.
- Apply SSH hardening (disable password auth, restrict ciphers).
- Configure unattended-upgrades or equivalent.

---
[Back to Overview](./OVERVIEW.md)
