# Defense in Depth

Multiple, independent layers protect Docker images and runtime from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Multi-stage builds** — Build stages MUST be separated from runtime stages. The runtime image MUST contain only what production needs.
2. **Pinned base images** — `FROM` lines MUST pin to immutable digests, not floating tags. Floating tags break reproducibility.
3. **HEALTHCHECK** — Every service image MUST declare `HEALTHCHECK` so the orchestrator detects a sick container without relying on an external probe.
4. **Vulnerability scan** — Images MUST be scanned (Trivy, Grype, or equivalent) at build time; high/critical findings MUST block the build.
5. **Non-root user** — Containers MUST run as a non-root user; this is a structural defense against accidental privilege misuse.
6. **Resource limits** — Memory and CPU limits MUST be set on every container; OOM behavior is part of correctness.
7. **Registry redundancy** — Pull-through caches and a secondary registry MUST exist so a single registry outage does NOT freeze deployment.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — An image that builds and runs locally is one signal; it tells you nothing about its behavior on the cluster.
- **Two is a tie** — Build green + scan clean but the deployed container's HEALTHCHECK failing in staging is the runtime dissent; the runtime is the deciding voter.
- **Three is a quorum** — Build/scan + container HEALTHCHECK + orchestrator-level readiness probe form the triple. All three MUST agree before promoting an image to production.

Example: an image that passes Trivy and builds clean but fails to start because of a missing locale or CA bundle — only the runtime probes catch it. Build success without runtime verification is one signal, never three.

---
[Back to Overview](./OVERVIEW.md)
