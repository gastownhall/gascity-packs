# Networking Configuration

### Network Modes

| Mode | Description | Use |
|:-----|:------------|:----|
| **bridge** (default) | Container interface attached to a Linux bridge | Most flexible; supports VLANs, firewall rules, standard networking |
| **routed** | Host routes traffic to/from container IP | Specific isolation requirements; requires host-side routing |
| **NAT** | Container uses private addressing with host-provided NAT | Internet-bound traffic from containers without public IPs |

### Bridge Configuration

```ini
net0: name=eth0,bridge=vmbr0,ip=10.0.0.10/24,gw=10.0.0.1,firewall=1,hwaddr=BC:24:11:XX:XX:XX
```

| Parameter | Purpose |
|:----------|:--------|
| `name` | Interface name inside container |
| `bridge` | Host bridge to attach |
| `ip` | Static IP with CIDR notation, or `dhcp` |
| `gw` | Default gateway |
| `firewall` | Enable Proxmox firewall integration |
| `hwaddr` | MAC address (auto-generated if omitted) |
| `tag` | VLAN tag for tagged traffic |
| `rate` | Bandwidth limit in MB/s |

### VLAN Segmentation

Separate container networks by security tier:

```ini
# Production database tier
net0: name=eth0,bridge=vmbr0,tag=100,ip=10.100.0.10/24,gw=10.100.0.1
# DMZ web tier
net0: name=eth0,bridge=vmbr0,tag=200,ip=10.200.0.10/24,gw=10.200.0.1
# Management network
net1: name=eth1,bridge=vmbr1,tag=10,ip=10.10.0.10/24
```

The host bridge must be configured to pass tagged traffic (typically as a trunk to the physical switch).

### Multiple Network Interfaces

```ini
net0: name=eth0,bridge=vmbr0,ip=10.0.0.10/24,gw=10.0.0.1
net1: name=eth1,bridge=vmbr1,ip=10.10.0.10/24
```

Use cases:

- Separate management and application traffic.
- Backend database networks isolated from frontend.
- Dedicated backup network for large data transfers.

### Bandwidth Limits

```ini
net0: name=eth0,bridge=vmbr0,ip=10.0.0.10/24,rate=100
```

`rate` specifies per-interface bandwidth limit in MB/s.

### Firewall Integration

Proxmox firewall applies rules at the host level for container traffic. Enable firewall in datacenter/cluster options. Define security groups with reusable rule sets. Apply groups to containers via GUI or API.

Container-level iptables rules also function but require coordination with host-level firewall to avoid conflicts.

### DNS Configuration

```ini
nameserver: 10.0.0.2
searchdomain: internal.example.com
```

Or rely on DHCP-provided DNS when using dynamic addressing. Containers requiring stable DNS resolution should use static nameserver configuration pointing to internal DNS infrastructure.

---
[Back to Overview](./OVERVIEW.md)
