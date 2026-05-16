# Defense in Depth

Multiple, independent layers protect DNS / domain infrastructure from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Multiple nameservers** — Every zone MUST have at least two nameservers, ideally on separate networks/providers.
2. **DNSSEC** — DNSSEC MUST be enabled on production zones; signed responses are an integrity check independent of the resolver path.
3. **Registrar locks** — Registrar lock and 2FA on the registrar account are required; domain hijacking is a controllable risk.
4. **Monitoring of records** — DNS records MUST be monitored externally (RIPE Atlas / DNSSpy / multi-region resolver checks) so quiet drift is detected.
5. **TTL discipline** — TTLs MUST be reviewed before changes (lower → cut over → raise); high TTLs hide rollouts AND rollbacks.
6. **Documented and versioned zone files** — Zone files MUST live in version control; portal-only edits are forbidden.
7. **Certificate monitoring** — TLS certificate expiry and chain MUST be monitored independently of issuance automation.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — A single nameserver is unsafe; a single registrar account is unsafe; a propagation check from a single resolver is one voter.
- **Two is a tie** — Two nameservers on the same provider share the provider's failure domain; an outage takes both.
- **Three is a quorum** — At least three resolvers, ideally across two providers, MUST be observable. The same applies to record monitoring: at least three vantage points (different ASes/regions) MUST agree on what the public DNS looks like before declaring a change live.

Example: until at least three geographically distinct resolvers all report the new record, the change is NOT live.

---
[Back to Overview](./OVERVIEW.md)
