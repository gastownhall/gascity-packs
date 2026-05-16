# Nested Virtualization and Docker Integration

### Enabling Nesting

```ini
features: nesting=1,keyctl=1
```

| Feature | Purpose |
|:--------|:--------|
| `nesting` | Enable nested container support |
| `keyctl` | Enable keyctl syscall for certain container runtimes |

**Security implications:**

- Additional attack surface through nested container escape.
- Complex cgroup hierarchy management.
- Resource accounting at multiple levels.

### Docker Inside LXC

| Driver | Kernel | Recommended |
|:-------|:-------|:------------|
| **overlay2** | 5.11+ | Yes — native overlay with unprivileged support |
| `fuse-overlayfs` | older | No — requires fuse device access |
| `vfs` | all | No — no copy-on-write, space inefficient |

Avoid BTRFS and ZFS storage drivers inside containers — use them at the Proxmox storage level instead.

```bash
# Inside LXC container
apt-get update && apt-get install -y docker.io
# Configure Docker for container environment
cat > /etc/docker/daemon.json << 'EOF'
{
  "storage-driver": "overlay2",
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF
systemctl restart docker
```

### Rootless Podman Alternative

Advantages:

- No daemon required.
- Rootless by default.
- Better security isolation.

```bash
apt-get install -y podman slirp4netns fuse-overlayfs
loginctl enable-linger $USER
systemctl --user start podman.socket
```

### Resource Accounting

Docker containers inside LXC consume the LXC container's resource allocation. The LXC cgroup limits apply to all processes including Docker containers. Monitor at both the LXC level and Docker level to understand actual utilization.

### Networking

Docker networking inside LXC works with some modes:

| Mode | Behavior |
|:-----|:---------|
| `bridge` | Docker creates its own bridge inside the container |
| `host` | Docker shares the LXC container's network namespace |
| `none` | No Docker networking; manually configure |

Port publishing from Docker inside LXC requires traffic to traverse both Docker and LXC networking layers. For complex networking, consider running Docker directly on hosts or in VMs.

---
[Back to Overview](./OVERVIEW.md)
