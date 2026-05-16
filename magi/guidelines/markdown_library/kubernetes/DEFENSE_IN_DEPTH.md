# Defense in Depth

Multiple, independent layers protect Kubernetes manifests and runtime from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Liveness, readiness, startup probes** — Every workload MUST declare all three probe types. Together they catch crashes, slow boots, and gradual degradation.
2. **Multiple replicas** — Production Deployments MUST run at least two (preferably three) replicas across distinct nodes; one replica is one point of failure.
3. **Pod disruption budgets** — Every critical workload MUST have a PDB so voluntary disruptions do NOT drain it below the safe minimum.
4. **Anti-affinity and topology spread** — Pods MUST be spread across nodes/zones; co-location is a single failure domain.
5. **Resource requests and limits** — CPU/memory requests AND limits MUST be set; unset means the scheduler is guessing and the kernel is the only enforcer.
6. **HPA or VPA** — Critical workloads MUST autoscale on a primary signal (CPU, RPS, queue depth).
7. **Observability** — Metrics + logs + traces MUST flow out of every workload (Prometheus, Loki/ELK, OpenTelemetry).

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — A single replica is the textbook anti-pattern. One replica is zero majority and zero quorum.
- **Two is a tie** — Two replicas survive a node failure but cannot establish a leader-election majority and cannot tolerate a rolling update without going to one.
- **Three is a quorum** — Three replicas across three failure domains are the minimum that preserves a quorum during a single-node loss AND a rolling update. Apply this to Deployments AND to any leader-elected component (etcd, ZooKeeper, etc.).

Example: a 2-replica StatefulSet on a 2-node cluster does NOT survive a node drain; bumping to 3 replicas across 3 nodes is the rule of three made literal.

---
[Back to Overview](./OVERVIEW.md)
