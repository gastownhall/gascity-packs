# Defense in Depth

Multiple, independent layers protect a WooCommerce store from a single failure. This is **failure-mode defense in depth** (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Seven Independent Layers of Defense

| Layer | Validation |
|:-----:|:-----------|
| 1 | **Staging mirror** — A staging environment MUST mirror production (theme, plugins, payment gateways) and MUST be the first place every change lands |
| 2 | **Automated backups** — Database + uploads + plugins MUST be backed up daily AND before any plugin/theme update; backups MUST be tested by performing a restore |
| 3 | **Plugin and core update discipline** — Updates MUST be applied on staging first, then production; auto-updates of paid extensions MUST be off in production |
| 4 | **Payment gateway monitoring** — Stripe/PayPal/etc. webhook arrival MUST be monitored independently of WooCommerce's order status |
| 5 | **Performance monitoring** — TTFB and checkout flow MUST be monitored synthetically; **checkout regressions are revenue regressions** |
| 6 | **Order and stock reconciliation** — A nightly job MUST reconcile Woo orders, payment-gateway records, and stock counts |
| 7 | **Malware and integrity scans** — File-integrity scans (Wordfence, Sucuri, or equivalent) MUST run on a schedule |

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority. Apply this rule whenever a decision in this domain depends on a check, a copy, a vote, or an actor that fails, drifts, or disagrees.

- **One is a claim** — A successful checkout in dev is one signal; it does **not** prove the production gateway is healthy.
- **Two is a tie** — Checkout-test pass + production order created without a corresponding gateway charge is the silent-failure mode; **reconciliation is the deciding voter**.
- **Three is a quorum** — Synthetic checkout + payment-gateway webhook + nightly reconciliation form the triple. **A revenue claim is real only when all three agree.**

**Example:** An order marked `completed` in Woo without a Stripe charge is two voters disagreeing with the third; **the gateway is the canonical truth**.

---
[Back to Overview](./OVERVIEW.md)
