# Defense in Depth

Multiple, independent layers protect a WordPress site from a single failure. This is **failure-mode defense in depth** (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Seven Independent Layers of Defense

| Layer | Validation |
|:-----:|:-----------|
| 1 | **Staging environment** — A staging copy MUST exist; theme/plugin/core changes go there first |
| 2 | **Backups with restore drills** — Daily database + uploads backups MUST be taken AND a restore MUST be exercised at least quarterly |
| 3 | **Update discipline** — Plugins, themes, and core MUST be updated on staging first; pinned versions MUST live in version control (Composer-managed where possible) |
| 4 | **File integrity monitoring** — Wordfence/Sucuri/equivalent MUST monitor for unexpected file changes |
| 5 | **Performance and uptime monitoring** — Synthetic checks MUST hit the production URL from multiple regions |
| 6 | **Structured error logs** — PHP errors and 5xx responses MUST be shipped to a log aggregator |
| 7 | **DNS and TLS monitoring** — Independent monitoring of DNS records and TLS expiry MUST exist |

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority. Apply this rule whenever a decision in this domain depends on a check, a copy, a vote, or an actor that fails, drifts, or disagrees.

- **One is a claim** — A working dashboard is one signal; it tells you the WP admin is up, **not** that the public site renders or that backups are working.
- **Two is a tie** — Public site up + admin up but backup job silently failing is the unmonitored single point of failure; **backup verification is the deciding voter**.
- **Three is a quorum** — Synthetic uptime + integrity scan + verified backup form the triple. **All three MUST agree before declaring the site healthy.**

**Example:** A backup script that completes with exit 0 every night but writes 0-byte archives — only a periodic restore drill catches it.

---
[Back to Overview](./OVERVIEW.md)
