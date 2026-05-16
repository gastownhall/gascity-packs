# Defense in Depth

Multiple, independent layers protect Inductive Automation Ignition v8.3 modules from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Gateway redundancy** — Production v8.3 Gateways MUST run as a redundant pair using the new redundancy model; resource scopes MUST be reviewed.
2. **Resource collections discipline** — `ResourceTypeMeta` + extension points MUST be used; do NOT bypass the resource model.
3. **Module signing and licensing** — Every module MUST be signed; license-aware modules MUST handle revocation gracefully.
4. **Protobuf RPC versioning** — Module RPC schemas MUST be versioned; breaking changes MUST go through additive evolution.
5. **Secrets API usage** — Secrets MUST come from the v8.3 Secrets API; never embed credentials in module config.
6. **Scripting error handling** — Every script MUST wrap external calls and emit structured logs.
7. **Designer and runtime parity** — Designer + Perspective session + Vision client behavior MUST all be exercised before declaring a feature done.
8. **Backup and redundancy monitoring** — Gateway backups + redundancy status + module health MUST be exported to external monitoring.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — A working module on Designer alone is one signal; runtime behavior in Perspective and Vision diverges.
- **Two is a tie** — Designer + one runtime surface (Perspective OR Vision) is still two signals; the third surface MUST be exercised before sign-off.
- **Three is a quorum** — Designer + Perspective + Vision (or for headless modules: Designer + Gateway scope + Client scope) form the canonical triple. All three MUST agree before declaring a v8.3 module change done.

Example: a component that renders correctly in Designer and Perspective but throws on a Vision client because of a JavaFX-specific dependency — only the third surface catches it.

---
[Back to Overview](./OVERVIEW.md)
