# Shakedown

### Mandate

Every automation that touches an integration boundary MUST provide a shakedown phase before handoff. A shakedown is the **first controlled, end-to-end execution of the automation under real operating conditions** — real subsystems, real credentials, real network, real filesystem — bounded to a controlled environment.

Shakedown answers one question: **does this automation actually work when every component runs together under real conditions?**

### Shakedown Validates Self-Healing Under Real Conditions

The self-healing principles (detect → correct → verify → execute → validate → clean) prove that automation **can** recover from known bad states. Shakedown proves that those recoveries **actually do** work against real subsystems. Self-healing is verified in isolation; shakedown is verified in composition.

Self-healing without shakedown is a claim; self-healing with a passing shakedown is evidence. **An automation that self-heals in preflight but fails in shakedown has self-healing that is theoretical, not real.**

### Preflight vs Shakedown vs Testing

| Phase | Purpose | Execution | Scope | Frequency | Question |
|:------|:--------|:----------|:------|:----------|:---------|
| Preflight | Readiness | Inspection only | Runtime prerequisites | Every execution | Can it run? |
| **Shakedown** | **Integration soundness** | **Real, controlled** | **Full integrated system** | **After significant change** | **Does it work?** |
| Testing | Behavior, performance | Real, at scale | Behavioral correctness, speed | Ongoing | Does it work correctly and well? |

### Failure Semantics

- **Preflight failure** — The automation is not ready to run. Fix the environment.
- **Shakedown failure** — The automation is not sound. Fix the code.
- **Test failure** — The automation is not correct or fast enough. Fix the implementation.

### Mandatory Triggers

- First-ever execution of newly built automation
- Major refactoring, architectural change, or subsystem replacement
- Infrastructure change — new deploy target, runtime upgrade, OS upgrade, base image change, database migration, cloud provider change
- Dependency upgrade with breaking-change potential
- Repair after a systemic failure — the repair itself is validated under integrated conditions
- Extended dormancy — automation that has not executed in a significant period and whose environment may have drifted

### Non-Triggers

- Routine execution of an unchanged automation — preflight covers this
- Minor bug fixes that do not alter integration points
- Configuration value changes within already-validated schemas
- Content or data updates that do not change execution paths

### Six Validation Surfaces

1. **Data flow integrity** — Inputs are received, parsed, and propagated through the full pipeline. Intermediate transformations produce structurally valid outputs. Final outputs arrive at the expected destination in the expected format. No data is silently dropped, truncated, or corrupted in transit.
2. **Subsystem communication** — Service-to-service calls connect, authenticate, and return expected response structures. Database connections establish, queries execute, results deserialize. Message queues, event buses, and IPC channels deliver and consume without loss or duplication. Filesystem operations succeed in the actual target environment with the actual permissions.
3. **Resource availability under load** — Memory allocation is stable across a representative execution pass. File handles, network sockets, and database connections are acquired and released correctly. Temporary resources are created and cleaned up. Concurrency primitives initialize and function without deadlock on first use.
4. **Configuration propagation** — Configuration values flow from source (file, environment, remote config store) to the components that consume them. Feature flags and environment-specific overrides activate as declared. Secrets and credentials are accessible at runtime — not just present, but actually usable by the components that need them.
5. **Error handling paths** — Known error conditions trigger the expected handling (retry, fallback, graceful degradation), not unhandled exceptions. Logging captures errors with sufficient context. Cleanup and rollback logic executes correctly on failure. Error propagation does not cascade into unrelated subsystems.
6. **Side-effect correctness** — External side effects occur exactly once and target the correct destination. Idempotency guarantees hold where claimed. No unintended side effects — no writes to the wrong table, no messages to the wrong queue, no mutations to shared state.

### Execution Principles

- **Conservative execution** — representative safe inputs, not edge cases, stress limits, or adversarial inputs
- **Progressive stress** — start with the simplest end-to-end path, add complexity incrementally, stop at the first failure and diagnose
- **Controlled environment** — real but bounded: isolated databases, sandbox API keys, test queues, staging endpoints
- **Observable execution** — verbose logging, full output capture, timing recorded, execution trace preserved
- **Known-good inputs** — inputs with known expected outputs, a small set of representative cases where "correct" is known
- **No optimization during shakedown** — note performance issues, log them, move on

### Execution Sequence

```text
Step 1: Confirm preflight passes — static prerequisites are met
Step 2: Initialize the controlled environment — sandbox, staging, isolated runtime
Step 3: Execute the simplest end-to-end path — happy path, minimal data
Step 4: Verify outputs match expectations — structural validity, correct destination
Step 5: Check for resource leaks or orphaned state — temp files, open handles, dangling locks
Step 6: Increase complexity incrementally — more data, more paths, more concurrency
Step 7: Record all observations — logs, outputs, timing, anomalies
Step 8: Classify results — pass, fail-blocking, fail-nonblocking, inconclusive
```

### Result Classification

| Outcome | Meaning |
|:--------|:--------|
| **pass** | Automation operates correctly as an integrated whole. Proceed to testing, optimization, or deployment. |
| **fail-blocking** | Integration fault preventing correct operation. Fix immediately. Re-run shakedown from step 1. |
| **fail-nonblocking** | Observed issue that does not prevent operation but requires attention. Log to issue tracker with full diagnostic context. Proceed with caution. |
| **inconclusive** | Environment or input limitations prevented validation of a critical path. Adjust and re-run the specific validation. |

### Required Artifacts (Four, No Exceptions)

1. **Execution log** — Full, timestamped log with all subsystem outputs captured
2. **Result summary** — Pass/fail classification per validation category
3. **Issue list** — Every anomaly observed, classified blocking/non-blocking/deferred, with reproduction context
4. **Environment snapshot** — Runtime and dependency versions, configuration state, infrastructure details at the time of shakedown — establishes the validated baseline

### Anti-Patterns (Forbidden)

- Skipping shakedown after a "small" change that touches an integration boundary — the most dangerous integration failures come from changes that seem small
- Treating shakedown as a comprehensive test suite — shakedown uses a small number of representative cases, not dozens of assertions
- Running shakedown in a non-representative environment — mocked services, in-memory databases, or environments that differ materially from target
- Optimizing during shakedown — optimization delays validation and introduces new changes that themselves require validation
- No record of shakedown results — a shakedown without artifacts is a shakedown that did not happen
- Writing shakedown artifacts to a system temp directory — artifacts live in a project-local scratch directory so they are preserved alongside the automation

---
[Back to Overview](./OVERVIEW.md)
