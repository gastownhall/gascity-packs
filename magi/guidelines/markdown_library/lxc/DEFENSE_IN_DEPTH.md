# Defense in Depth

Multiple, independent layers protect LXC / LXD container hosts from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Snapshots before change** — Every mutating action (config change, package install, kernel upgrade) MUST be preceded by a snapshot.
2. **Backups shipped offsite** — Container images and bind-mounted data MUST be shipped to an off-host target (NFS, S3-compatible, ZFS replication).
3. **Config as code** — Profiles and instance configs MUST live in version control; manual `lxc config` edits are forbidden.
4. **Monitoring and alerts** — CPU, memory, disk, and process state MUST be exported (Prometheus node-exporter or equivalent) and alerted.
5. **Idempotent provisioning** — Provisioning MUST be expressed in Ansible / cloud-init; re-running MUST converge.
6. **HA or clustered targets** — Critical workloads MUST run on an LXD cluster or have an automated failover container ready on a peer host.
7. **Shakedown** — The §20 post-provision shakedown gates every container before declaring it production-ready.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — A working container is one signal; losing the host loses it.
- **Two is a tie** — Two replicas across two hosts lose quorum with one outage and cannot tolerate a maintenance window without going to one.
- **Three is a quorum** — Snapshot + off-host backup + secondary host (or LXD cluster of three or more nodes) form the triple. Recovery MUST be possible from a majority of these even if any one is destroyed.

Example: a snapshot is useless if the host disk dies; the off-host backup is the second voter; a peer host primed to start the workload is the third.

---
[Back to Overview](./OVERVIEW.md)
