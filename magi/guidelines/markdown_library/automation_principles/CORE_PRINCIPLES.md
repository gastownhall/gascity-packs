# Core Principles

These guidelines define strict, reliable, and repeatable patterns for automation systems, optimizing for:

- **Self-Sufficiency**: Every script runs to completion on a fresh system without manual intervention, prerequisite documentation, or implicit assumptions about environment state
- **Deterministic Execution**: Given identical inputs and starting conditions, automation produces identical outcomes; randomness and environmental variance are explicitly handled
- **Failure Isolation**: Individual component failures do not cascade; automation contains failures, recovers where possible, and provides actionable diagnostics where recovery fails
- **Operational Transparency**: Every action, decision, and outcome is observable through structured logging; silent failures are architectural defects
- **Minimal Footprint**: Automation installs only what is required, cleans up after itself, and leaves systems in a known-good state regardless of execution path

### The Golden Rule

**If you have to run a manual command to make automation work, that command belongs IN the automation.**

This rule has no exceptions. README prerequisites, "make sure X is installed" notes, setup scripts that must run before the real script, and troubleshooting guides that describe manual fixes — all indicate incomplete automation. Every manual step is a failure mode waiting to happen, a tribal knowledge dependency, and a barrier to scaling operations.

### Scope and Application

These principles apply universally to:

- Deployment scripts (application, infrastructure, configuration)
- Build and compilation pipelines
- Environment provisioning and teardown
- Data migration and transformation jobs
- Scheduled tasks and cron jobs
- Developer environment setup
- Testing and validation automation
- Monitoring and alerting configuration
- Backup and recovery procedures
- Any repeatable operation that humans currently perform manually

The technology stack is irrelevant. Bash, Python, PowerShell, Ansible, Terraform, Make — all must adhere to these principles. The language is a tool; the discipline is the constant.

### The Cost of Manual Intervention

Manual steps impose compounding costs:

**Knowledge decay**: The person who knows the manual step leaves, retires, or forgets. The step becomes tribal knowledge that fails during incident response when it matters most.

**Error amplification**: Manual steps are performed differently each time. Subtle variations accumulate into significant drift. "It works on my machine" becomes "it worked last deployment."

**Scale prohibition**: Manual steps that take five minutes for one server take five hours for sixty servers. Operations that cannot scale are operations that will eventually fail.

**Audit impossibility**: Manual steps have no logs, no versioning, and no reproducibility. Compliance audits require evidence of what happened; manual steps provide only memories.

**Recovery obstruction**: When automation fails partway, manual steps must be remembered, sequenced, and executed under pressure. Partial automation with manual gaps is worse than no automation at all.

---
[Back to Overview](./OVERVIEW.md)
