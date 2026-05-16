# Clustering and High Availability

### Cluster Architecture

RabbitMQ clusters share users, vhosts, exchanges, bindings, and runtime state:

- All nodes know all topology metadata.
- Queues exist on the node that declared them (unless replicated).
- Clients can connect to any node.
- Cluster requires reliable, low-latency network.

### Node Types

| Node | Storage | Requirement | Use case |
|:-----|:--------|:------------|:---------|
| Disc | Metadata on disk | At least one per cluster | Standard cluster nodes |
| RAM | Metadata in memory only | Cannot be sole node | Large clusters for faster startup |

### Quorum Queue Replication

Quorum queues replicate messages across nodes:

- Configure replication factor (e.g., 3 for three-node cluster).
- Raft consensus ensures consistency.
- Tolerates minority node failure.
- Automatic leader election on failure.

**This is the HA mechanism for production. Classic mirrored queues are deprecated.**

### Load Balancing

Distribute client connections across cluster nodes:

- Use TCP load balancer (HAProxy, nginx, cloud LB).
- Health checks against RabbitMQ management API.
- Connection affinity not required; any node can serve any request.
- Consider connection limits per node when sizing.

### Network Partitions

Partitions occur when cluster nodes cannot communicate:

| Strategy | Behavior | Recovery | Use case |
|:---------|:---------|:---------|:---------|
| `pause_minority` | Minority nodes pause, preventing split-brain | Automatic when partition heals | **Safest default for production** |
| `autoheal` | Automatic merge after partition | Automatic, may lose messages | Availability over consistency |
| `ignore` | No automatic action | Manual intervention required | Special requirements with runbooks |

Plan for partition scenarios in your runbook.

### Cluster Sizing

| Environment | Nodes | Replication | Tolerance |
|:------------|:-----:|:------------|:---------:|
| Development | 1 | None | None |
| Production (basic HA) | 3 | Quorum factor 3 | 1 node failure |
| Production (high availability) | 5+ | Quorum factor 3–5 | 2+ node failures |

Use **odd node counts** for simpler quorum calculations.

### Federation

Link brokers across WAN or separate clusters:

- Multi-datacenter deployments.
- Cluster-to-cluster message flow.
- WAN message distribution.

| Federation type | Description | Direction |
|:----------------|:------------|:----------|
| Exchange federation | Federate specific exchanges | Unidirectional or bidirectional |
| Queue federation | Federate specific queues; messages consumed from upstream when downstream has consumers | Pull-based |

### Shovel

Move messages between brokers:

- Migration between clusters.
- One-way message replication.
- Protocol bridging.

Configuration declares source broker URI and queue, destination broker URI and exchange, and acknowledgment after successful delivery.

---
[Back to Overview](./OVERVIEW.md)
