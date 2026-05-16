# Container vs Virtual Machine Selection

### When to Use LXC Containers

- Workload requires Linux and the host runs a compatible kernel version.
- Performance overhead of full virtualization is unacceptable.
- Density matters — running 50+ workloads on a single host.
- Workload does not require custom kernel modules or kernel version pinning.
- Security requirements satisfied by namespace isolation and AppArmor confinement.
- Network performance is critical; containers share the host network stack with minimal overhead.

### When to Use Virtual Machines

- Workload runs a non-Linux operating system (Windows, BSD, proprietary appliances).
- Kernel isolation is mandatory — workload requires different kernel version or custom modules.
- Compliance frameworks mandate hardware-level isolation (some PCI-DSS interpretations, classified environments).
- Workload behavior is untrusted and container escape risk is unacceptable even with unprivileged containers.
- Nested virtualization with full hardware passthrough is required.
- Workload requires UEFI, Secure Boot, or TPM emulation.

### Hybrid Patterns

Many environments benefit from both:

- VMs for network boundaries and untrusted workloads.
- LXC containers within VMs for density where isolation requirements permit.
- LXC containers directly on Proxmox hosts for trusted infrastructure services.

Document the rationale for each workload's placement. Decisions should be traceable to security requirements, performance characteristics, or operational constraints — not convenience or historical accident.

---
[Back to Overview](./OVERVIEW.md)
