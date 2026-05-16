# Runner and Agent Security

### Ephemeral Runners

Use ephemeral runners that are provisioned fresh for each job and destroyed after completion. Persistent runners accumulate state (cached credentials, build artifacts, temporary files) that can leak between jobs from different repositories or different trust levels.

Cloud-hosted CI defaults: GitHub-hosted runners, GitLab SaaS runners. Self-hosted runners must be configured for ephemeral behavior.

### Trust-Level Isolation

**Self-hosted runners must not be shared between public and private repositories.** A malicious PR to a public repository executes arbitrary code on the runner, which may have access to private repository secrets or network access to internal infrastructure. Isolate runner pools by trust level.

### Container/VM Isolation

Self-hosted runners must run pipeline jobs in isolated containers or VMs, not directly on the host OS. Direct host execution allows pipeline code to access the host filesystem, network, and other processes. Container isolation (Docker-in-Docker, Kubernetes pods) limits the blast radius of malicious pipeline code.

### Update Cadence

Keep self-hosted runner software updated to the latest version. Automate runner image updates on a weekly cadence at minimum.

### Resource Monitoring

Monitor runner resource usage (CPU, memory, disk, network) and alert on anomalies. Cryptominers, data exfiltration, and denial-of-service attacks from compromised pipelines manifest as abnormal resource consumption. Network egress monitoring detects unexpected outbound connections from runners.

---
[Back to Overview](./OVERVIEW.md)
