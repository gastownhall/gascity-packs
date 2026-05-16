# Self-Healing Architecture

Self-healing automation detects failures in its execution environment and corrects them automatically before proceeding with primary objectives. This is not error handling — error handling responds to failures. Self-healing prevents failures by ensuring prerequisites exist before operations that depend on them.

### Detection Before Action

Every operation that depends on external state must verify that state before attempting the operation:

- **Resource existence** — Directories, files, users, groups, network endpoints, services, packages must be verified present before use.
- **Resource accessibility** — Existence is insufficient; read/write/execute permissions, network reachability, service responsiveness, and credential validity must be confirmed.
- **Resource correctness** — Present and accessible resources must be in the expected state — correct versions, valid configurations, healthy status.

### Correction Before Failure

When detection reveals missing or incorrect prerequisites, automation must correct the condition:

- **Missing resources** — Create directories, install packages, provision services, generate configuration files, establish network routes.
- **Incorrect permissions** — Adjust ownership, modify access control lists, request elevated privileges through proper channels, configure security contexts.
- **Invalid state** — Restart services, regenerate corrupted files, re-download incomplete artifacts, rebuild invalid caches.

### Graceful Degradation

Not all corrections are possible. Self-healing automation recognizes when correction fails and degrades gracefully:

- **Partial functionality** — If a non-critical component cannot be corrected, continue with reduced capability and log the degradation clearly.
- **Safe termination** — If a critical component cannot be corrected, terminate immediately with explicit diagnostics rather than proceeding into undefined behavior.
- **Recovery guidance** — When termination is necessary, provide specific, actionable guidance for manual intervention — not generic error messages.

### The Self-Healing Loop

```
┌─────────────────────────────────────────────────────────────┐
│                    For Each Operation                        │
├─────────────────────────────────────────────────────────────┤
│  1. Detect: Check all prerequisites for the operation        │
│  2. Correct: Fix any missing or invalid prerequisites        │
│  3. Verify: Confirm corrections succeeded                    │
│  4. Execute: Perform the primary operation                   │
│  5. Validate: Confirm the operation achieved its objective   │
│  6. Clean: Remove temporary resources created during healing │
└─────────────────────────────────────────────────────────────┘
```

This loop applies recursively. The correction step may itself require prerequisites that must be detected and corrected. A script installing Docker must first ensure package managers are available; ensuring package managers may require network connectivity; ensuring network connectivity may require DNS configuration.

### Check-Then-Act Idempotency

```bash
if [[ ! -d "${TARGET_DIR}" ]]; then
    mkdir -p "${TARGET_DIR}"
    chmod 755 "${TARGET_DIR}"
fi
```

---
[Back to Overview](./OVERVIEW.md)
