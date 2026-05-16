# Required Practices

### Always Do

- Use unprivileged containers for all workloads unless documented exception exists.
- Define explicit memory, CPU, and I/O limits for every container.
- Version control all template creation scripts and configuration snippets.
- Apply security updates within 72 hours of release for critical vulnerabilities.
- Configure centralized logging for all containers.
- Implement monitoring with alerting for resource exhaustion and failures.
- Document container purpose, owner, and dependencies in description field.
- Test backup restoration quarterly for critical containers.
- Use static IPs or documented DHCP reservations for infrastructure containers.
- Apply principle of least privilege for all resource access and capabilities.
- Review and remove unused containers, templates, and storage monthly.
- Maintain runbooks for common operational procedures.
- Configure boot order reflecting actual service dependencies.
- Use shared storage for containers requiring migration capability.
- Separate container networks by security tier using VLANs.
- Plan cluster capacity for N-1 node failure tolerance.
- Run a §20 shakedown after every provisioning event.

---
[Back to Overview](./OVERVIEW.md)
