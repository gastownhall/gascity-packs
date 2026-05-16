# Defense in Depth

Multiple, independent layers protect Inductive Automation Ignition v8.1 modules from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Gateway redundancy** — Production Gateways MUST run as a redundant pair; a single Gateway is a single point of failure.
2. **Module signing** — Every module MUST be signed; unsigned modules MUST NOT be installed in production.
3. **Scripting error handling** — Every Jython script MUST wrap external calls in `try/except` and log via `system.util.getLogger`. `bare except: pass` is forbidden.
4. **Designer and runtime parity** — Behavior MUST be tested in both Designer preview AND runtime client/perspective; designer-only success is one signal.
5. **Backup and restore discipline** — Gateway backups MUST be scheduled AND restore-tested.
6. **Tag historian redundancy** — Historian provider MUST replicate to a secondary store.
7. **Monitoring of Gateway status** — Gateway status, redundancy state, and module health MUST be exported to an external monitoring system.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — A single Gateway is unsafe; its loss takes the entire SCADA stack offline.
- **Two is a tie** — Primary + backup Gateway with a failed health check between them split-brain on automatic failover.
- **Three is a quorum** — Primary + backup + an independent witness (external monitoring, peer Gateway, or operator dashboard) form the canonical triple. Failover decisions MUST require majority agreement that the primary is down.

Example: a network blip that makes the backup believe the primary is dead — without a third witness, the backup takes over while the primary still serves clients, causing tag and alarm divergence.

---
[Back to Overview](./OVERVIEW.md)
