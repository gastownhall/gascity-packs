# Template Management

### Template Selection Criteria

Templates determine the available package ecosystem, init system, default security posture, and long-term support availability.

| Distro | Use Case | Version | Support |
|:-------|:---------|:--------|:--------|
| **Debian** | Long-term stability, extensive documentation, Proxmox base | 12 | LTS until 2028 |
| **Ubuntu** | Broader package availability, newer software | 22.04 LTS | LTS until 2027 |
| **Alpine** | Minimal footprint for single-purpose containers | 3.19 | musl libc compatibility |
| **Rocky / Alma** | RHEL compatibility for enterprise software | 9 | Enterprise lifecycle |

### Official Templates via `pveam`

```bash
pveam update
pveam available --section system
pveam download local debian-12-standard_12.2-1_amd64.tar.zst
```

### Custom Template Creation

Create custom templates when:

- Standard templates lack required packages or configurations.
- Security hardening must be baked into the base image.
- Organizational compliance requires specific baseline configurations.
- Reproducibility demands version-pinned package installations.

Workflow:

1. Create container from official template.
2. Apply required configurations, packages, and hardening.
3. Remove machine-specific identifiers (SSH host keys, machine-id).
4. Clean package caches and temporary files.
5. Stop container and create template backup.

```bash
#!/bin/bash
# Template creation workflow
pct create 9000 local:vztmpl/debian-12-standard_12.2-1_amd64.tar.zst \
    --hostname template-base --memory 2048 --cores 2 \
    --rootfs local-lvm:8 --net0 name=eth0,bridge=vmbr0,ip=dhcp \
    --unprivileged 1
pct start 9000
pct enter 9000
# Apply configurations
apt-get update && apt-get upgrade -y
apt-get install -y monitoring-agent security-tools
# Remove machine-specific identifiers
rm -f /etc/ssh/ssh_host_* /etc/machine-id /var/lib/dbus/machine-id
truncate -s 0 /etc/machine-id
apt-get clean && rm -rf /var/lib/apt/lists/*
exit
pct stop 9000
vzdump 9000 --compress zstd --mode stop --storage local
```

### Template Versioning

Pattern: `distro-version-purpose-vYYYY.MM.tar.zst`.

| Correct | Forbidden |
|:--------|:----------|
| `debian-12-hardened-v2026.02.tar.zst` | `debian-latest.tar.zst` |

- Maintain changelog documenting differences from base template.
- Store template creation scripts in version control.
- Rebuild templates monthly or upon critical security updates.
- Retain previous template versions until all dependent containers are migrated.

### Template Storage

- Store templates on shared storage accessible to all cluster nodes.
- Use compression (zstd preferred) to reduce storage and transfer time.
- Implement retention policies; templates older than 6 months without active containers are candidates for removal.
- Document template provenance — base image, modifications, security patches.

---
[Back to Overview](./OVERVIEW.md)
