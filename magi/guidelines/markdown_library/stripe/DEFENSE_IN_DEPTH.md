# Defense in Depth

Multiple, independent layers protect the Stripe payment integration from a single failure. This is **failure-mode defense in depth** (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Idempotency keys** — Every charge / refund / payout request MUST send an `Idempotency-Key`. Network retries without idempotency keys cause duplicate charges.
2. **Webhook signature verification** — Stripe webhooks MUST be verified with the signing secret; unsigned events MUST be rejected.
3. **Event-driven reconciliation** — The application MUST treat webhooks as the source of truth for state changes, **not API responses** — the API call may have succeeded after the client gave up.
4. **Nightly reconciliation** — A nightly job MUST diff Stripe's records against the local ledger. Drift MUST raise alerts.
5. **Retry with exponential backoff** — Outbound Stripe calls MUST retry with backoff on 5xx and on rate-limit responses.
6. **Dispute and Radar monitoring** — Disputes and Radar holds MUST be ingested and surfaced to operators within hours.
7. **Test-mode parity** — Every change MUST be exercised against a Stripe test account before production rollout.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority. Apply this rule to payment correctness.

- **One is a claim** — A successful API response is one signal; the client may have lost the response and retried, creating a duplicate.
- **Two is a tie** — API success + idempotency key is two signals that the side effect happened once; but neither tells you the customer's actual ledger entry.
- **Three is a quorum** — API response + matching webhook event + nightly reconciliation form the **canonical triple for payment correctness**. **A charge is only "really" applied when all three records agree.**

**Example:** A `200 OK` from `/v1/charges`, a `charge.succeeded` webhook, and a nightly reconciliation row that ties out — three witnesses, all required, before declaring revenue recognized.

---
[Back to Overview](./OVERVIEW.md)
