# Security Hardening

### Unprivileged Container Fundamentals

Unprivileged containers use Linux user namespaces to map container UIDs to unprivileged host UIDs:

- Container root (UID 0) maps to an unprivileged host UID (e.g., 100000).
- Container UID range (0–65535) maps to host range (100000–165535).
- Host resources owned by real root remain inaccessible even if container is compromised.

Mapping configuration in `/etc/pve/lxc/<vmid>.conf`:

```ini
unprivileged: 1
lxc.idmap: u 0 100000 65536
lxc.idmap: g 0 100000 65536
```

Custom mapping for specific UIDs:

```ini
lxc.idmap = u 0 100000 1000
lxc.idmap = u 1000 1000 1
lxc.idmap = u 1001 101001 64535
```

### AppArmor Profiles

Proxmox applies AppArmor profiles to LXC containers by default. Profiles restrict mount operations, network configuration capabilities, access to host `/proc` and `/sys` entries, and module loading.

| Profile | Level |
|:--------|:------|
| `lxc-container-default` | Standard |
| `lxc-container-default-cgns` | Standard with cgroup namespace |
| `custom-hardened` | Strict — organization-specific restrictions |

```ini
lxc.apparmor.profile = lxc-container-default-cgns
```

Custom profile excerpt:

```text
profile lxc-container-hardened flags=(attach_disconnected,mediate_deleted) {
  #include <abstractions/lxc/container-base>
  # Deny specific dangerous operations
  deny mount fstype=proc -> /proc/,
  deny mount fstype=sysfs -> /sys/,
  deny /proc/sys/kernel/** w,
  # Allow specific paths
  /usr/bin/myapp r,
  /var/lib/myapp/** rw,
}
```

**Do not disable AppArmor to "fix" application issues; investigate the specific denial and create appropriate exceptions if warranted.**

### Seccomp Filtering

Default Proxmox profiles block dangerous syscalls while permitting normal operation. Custom profiles can further restrict syscalls for single-purpose containers:

```ini
lxc.seccomp.profile = /usr/share/lxc/config/common.seccomp
```

### Linux Capabilities

| Capability | Risk | Notes |
|:-----------|:-----|:------|
| `CAP_SYS_ADMIN` | High | Near-root equivalent |
| `CAP_SYS_MODULE` | High | Kernel module loading |
| `CAP_SYS_RAWIO` | High | Raw I/O operations |
| `CAP_DAC_READ_SEARCH` | Medium | Bypass file permissions |
| `CAP_NET_ADMIN` | Medium | Network configuration |
| `CAP_NET_BIND_SERVICE` | Low | Bind ports below 1024 (default kept) |

```ini
# Drop dangerous capabilities
lxc.cap.drop = sys_admin sys_module sys_rawio
# Keep only required capabilities
lxc.cap.keep = net_bind_service setuid setgid
```

Grant additional capabilities only with documented justification.

### Filesystem Security

- Mount sensitive host directories read-only when container access is required.
- **Never bind-mount `/etc`, `/var`, or `/root`** from the host.
- Use dedicated volumes for persistent data rather than host bind mounts.
- Ensure bind-mounted directories have appropriate ownership matching container UID mapping.

### Network Security

- Place containers on appropriate VLANs matching their security tier.
- Use Proxmox firewall to restrict inter-container and external traffic.
- Containers should not have direct internet access unless required.
- Implement egress filtering for containers with internet access.
- Consider network namespaces for additional isolation between containers on the same host.

---
[Back to Overview](./OVERVIEW.md)
