# Defense in Depth

Multiple, independent layers protect Netlify deployments from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Preview deploys per PR** — Every PR MUST produce a deploy preview; the preview URL MUST be smoke-tested before merge.
2. **Build cache validation** — Builds MUST be reproducible without cache; nuke-cache reruns MUST pass periodically.
3. **Locked Node and package manager** — `.nvmrc` and a locked package manager (`.npmrc` / `pnpm-lock`) MUST pin runtime versions.
4. **Environment variable parity** — Production and preview env vars MUST be reviewed for parity; diffs MUST be intentional and documented.
5. **Rollback to prior deploy** — Netlify's instant rollback MUST be exercised at least quarterly so the muscle memory exists during incidents.
6. **Synthetic monitoring** — Uptime checks (Pingdom, Better Uptime, Datadog Synthetics) MUST hit the production URL from multiple regions.
7. **DNS and certificate monitoring** — Certificate expiry and DNS records MUST be monitored independently of Netlify's own UI.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — A successful build in Netlify's UI is one signal; it does NOT prove the deployed site renders.
- **Two is a tie** — Build green + preview URL 200 OK but a synthetic monitor failing from a second region is the network-path dissent; the synthetic check wins.
- **Three is a quorum** — Build success + preview-URL smoke + multi-region synthetic monitor form the triple. All three MUST agree before declaring a deploy healthy.

Example: a build that succeeds but ships a broken redirect rule passes the build voter, fails the smoke voter, and is overridden by both — never trust the build alone.

---
[Back to Overview](./OVERVIEW.md)
