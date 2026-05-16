# Cluster Architecture and Sizing

### Node Pool Strategy

Separate workloads by resource profile and operational requirements using multiple node pools:

| Pool | Purpose | Constraints |
|:-----|:--------|:------------|
| **System** | Cluster-critical components (CoreDNS, metrics-server, ingress controllers) | Taint `CriticalAddonsOnly=true:NoSchedule`; minimum 3 nodes spread across zones |
| **General** | Standard application workloads | Aggregate requirements + 30% headroom for rolling updates and burst capacity |
| **Specialized** | GPU workloads, memory-intensive processing, specific VM SKUs | Apply taints to prevent general scheduling; applications use tolerations to target |

### Node Sizing

- Prefer fewer larger nodes over many small nodes — reduces scheduling overhead and improves bin packing.
- **Minimum 4 vCPU / 16 GB RAM** for general workload nodes; smaller nodes waste resources on system overhead.
- Maximum node size balances blast radius (node failure impact) against efficiency.
- Account for system reservations: kubelet, OS, and eviction thresholds consume resources before pods.

### Availability Zone Distribution

- Spread node pools across all available zones (three in most Azure regions).
- Configure pod topology spread constraints to distribute replicas across zones.
- Use zone-aware storage classes for stateful workloads.
- Accept cross-zone network latency (~1–2 ms) as the cost of zone redundancy.

### Cluster Networking Mode

| Mode | When to Use |
|:-----|:------------|
| **Azure CNI Overlay** (recommended) | Most workloads. Pod IPs from overlay network; node IPs from VNet. Simpler IP address management |
| Azure CNI dynamic IP allocation | Pods require direct VNet connectivity or existing NSGs must apply to pod traffic |
| Kubenet | Avoid for production unless specific constraints require it |

### Control Plane Configuration

- Enable private cluster for production; API server accessible only from private networks.
- Configure authorized IP ranges for API server access if public endpoint required.
- Enable Defender for Containers for threat detection.
- Use managed identity for cluster operations; never service principal with static credentials.

---
[Back to Overview](./OVERVIEW.md)
