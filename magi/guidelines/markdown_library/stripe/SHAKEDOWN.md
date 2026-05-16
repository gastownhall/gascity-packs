# Shakedown — Integration Validation

### Definition

A Stripe shakedown is a **mandatory, end-to-end test-mode round-trip against the real Stripe API**, executed with test keys, test webhook signing secrets, and Stripe's published test cards before any **live-mode cutover** or any change that touches webhook endpoints, product/price catalog, payment flows, subscription lifecycle, or refund/dispute handling.

The shakedown proves the integration executes correctly as an integrated whole. **It is not a unit test, not a load test, not a coverage exercise.**

**Shakedown must pass in Stripe test mode before live-mode traffic is enabled on any modified integration path.** A shakedown that has not passed is a release blocker. Live-mode activation without a green shakedown is a policy violation.

| Phase | Question |
|:------|:---------|
| Preflight | Is the environment ready to attempt Stripe calls? (test keys loaded, webhook signing secret present, `STRIPE_API_VERSION` pinned, Stripe CLI reachable, database migrations applied) |
| **Shakedown** | **Does the integration execute end-to-end under real Stripe test-mode conditions?** |
| Testing | Is the integration behaviorally correct across the full input space? |

### Mandatory Triggers

Shakedown is mandatory before any of the following reach live mode:

- First-ever deployment of a new Stripe integration.
- Any change to a webhook endpoint URL, signature verification logic, event routing, or deduplication store.
- Any Stripe API version bump (the pinned `apiVersion` value changes).
- Any change to the product or price catalog that the application reads, writes, or reconciles against.
- Any change to checkout session creation, PaymentIntent creation, confirmation flow, or 3DS handling.
- Any change to subscription creation, plan change, trial logic, dunning configuration, or proration behavior.
- Any change to refund issuance, dispute evidence submission, or Early Fraud Warning handling.
- Any `stripe-node`, `stripe-python`, `stripe-go`, or Stripe SDK version upgrade (major or minor).
- Any infrastructure change that moves webhook traffic: reverse proxy swap, WAF rule change, new ingress path, new API gateway, DNS change on the webhook host.
- Restored deployment after a payment-related incident or rollback.
- Extended dormancy — any integration that has not processed live traffic in a period long enough for API version, webhook endpoint, or key configuration to have drifted.

### Non-Triggers

- Routine deployments that do not touch Stripe API calls, webhook handling, or persisted payment state.
- Copy changes on customer-facing Stripe Elements container markup.
- Appearance API tweaks that do not change Elements initialization or confirmation flow.
- Log level adjustments, metric name changes, observability-only modifications.
- Dashboard-only Stripe configuration reads that do not change application code paths.

### Validation Categories

1. **Stripe API client auth** — the API client authenticates with the configured test secret key, executes at least one authenticated read (`stripe.accounts.retrieve` or `stripe.balance.retrieve`), and **rejects the response if the account ID or `livemode` flag does not match the expected test environment**.
2. **Webhook endpoint signature validation** — a real Stripe test-mode event is delivered to the webhook endpoint via Stripe CLI forward or a real test-mode trigger. Handler verifies `Stripe-Signature` against the actual `whsec_` test signing secret using `stripe.webhooks.constructEvent` against the **raw request body**. Verification must pass on a valid event and **reject a tampered event**.
3. **Database persistence of payment state** — after a PaymentIntent transitions to `succeeded` via webhook, the local order row reflects PaymentIntent ID, amount in smallest currency unit, currency, charge ID, status. Re-running the shakedown does not create duplicate rows — the event ID dedup store is consulted and honored.
4. **Accounting ledger consistency** — for every completed payment, refund, dispute processed during the shakedown, the local ledger records the Stripe `balance_transaction` ID, net amount after fees, Stripe fee amount. **The sum of local ledger entries reconciles exactly** against the Stripe balance transactions list for the shakedown time window.
5. **Notification dispatch idempotency** — customer-facing notifications fire **exactly once** per underlying Stripe event. A duplicate webhook delivery for the same `event.id` does not produce a duplicate email, SMS, or push notification.
6. **Checkout round-trip** — a `checkout.Session` is created server-side with a real test-mode price ID, customer completes payment via `4242...` test card, `checkout.session.completed` is delivered, fulfillment is triggered by the webhook (not by the success URL), the order is provisioned in the database.
7. **3DS challenge path** — a PaymentIntent confirmation with `4000002500003155` transitions to `requires_action`, the client handles the 3DS challenge, Stripe posts `payment_intent.succeeded` on completion, the handler processes the successful outcome. **`requires_action` is exercised as a normal path, not as an error.**
8. **Idempotency key dedup under retry** — a mutating call (refund, PaymentIntent creation) is executed, then immediately retried with the same idempotency key. The second call returns Stripe's cached response. **No duplicate refund, charge, or transfer exists on the Stripe side.**
9. **Subscription lifecycle** — a test-mode subscription is created with a trial period, a Stripe Test Clock is advanced through `trial_will_end`, trial-to-active transition, `invoice.paid`, a simulated payment failure producing `past_due`, Smart Retry execution, and final cancellation. Each transition produces the expected application access state change.
10. **Refund flow** — a full and a partial refund are issued via the Refunds API with deterministic idempotency keys. `charge.refunded` is received, the local order and ledger reflect the refund, and a duplicate refund request with the same key returns the cached response without creating a second refund.
11. **Dispute webhook** — a test-mode dispute is triggered via `stripe trigger charge.dispute.created`. The handler persists the dispute record, pauses fulfillment for the affected order, captures the evidence submission deadline.
12. **Product/price catalog sync** — the price and product IDs referenced by the application exist in the live catalog with the ID shape the application expects (`prod_`, `price_`) and with the `active` flag set. **Stale or mistyped IDs are caught before cutover.**
13. **Customer Portal session creation** — a billing portal session is created server-side for a test customer and the returned URL resolves. The configured allowed actions in the Stripe Dashboard match the UI expectations.

### Execution Principles

- **Conservative execution** — Stripe's published test cards and minimal amounts (1.00 USD or currency equivalent). No fuzzed card numbers, no amount randomization, no customer PII.
- **Progressive stress** — exercise the simplest happy path first (single PaymentIntent, single webhook delivery). Expand incrementally to 3DS, retries, refund, subscription lifecycle, dispute. Stop at the first failure and diagnose before proceeding.
- **Controlled environment** — test mode API keys only. Test mode webhook signing secret only. Test Stripe CLI listener or a dedicated test-mode webhook endpoint. **Never point the shakedown at a live endpoint or live key.**
- **Observable execution** — every Stripe API call, every webhook delivery, every handler invocation logged with request ID, event ID, idempotency key, resulting PaymentIntent/Subscription/Refund ID. Stripe request IDs preserved for correlation with the Stripe Dashboard.
- **Known-good inputs** — fixed test cards (`4242...` success, `4000002500003155` 3DS, `4000000000000002` decline), fixed amounts, fixed price IDs. No generated data.
- **No optimization during shakedown** — do not tune retry windows, adjust batch sizes, or rewrite the webhook dispatcher during shakedown. Optimization introduces changes that themselves require shakedown.

### Execution Pattern

1. Confirm preflight passes — test keys resolve, webhook signing secret loaded, `apiVersion` pinned, database reachable, Stripe CLI installed and authenticated to the test mode account.
2. Initialize the controlled environment — clean test-mode webhook deduplication cache for the shakedown time window, clear shakedown order rows from the database, start the Stripe CLI listener forwarding to the local or staging webhook endpoint.
3. Execute the simplest end-to-end path — create a PaymentIntent with `4242` test card, confirm, verify `payment_intent.succeeded` is delivered, verify signature, verify deduplication, verify database row created, verify notification dispatched once.
4. Verify outputs — Stripe Dashboard shows the PaymentIntent in `succeeded` state with the expected amount and metadata; local database row matches; ledger row matches the Stripe `balance_transaction`.
5. Check for leaks and orphans — no duplicate database rows, no orphaned PaymentIntents, no webhook events in the dead-letter queue, no unprocessed notification jobs.
6. Increase complexity — 3DS challenge flow, idempotency retry, full refund, partial refund, subscription creation with Test Clock advancement, dispute trigger. Re-verify persistence, ledger, notifications after each addition.
7. Record all observations — full Stripe request IDs, event IDs, timings, anomalies, dashboard screenshots, database snapshots, ledger totals.
8. Classify results — `pass`, `fail-blocking`, `fail-nonblocking`, `inconclusive`.

### Result Classification

| Outcome | Trigger |
|:--------|:--------|
| `pass` | All validation categories succeeded — proceed to live-mode cutover |
| `fail-blocking` | Signature verification rejected valid events; idempotency produced duplicate charges; ledger did not reconcile; webhook deduplication races produced double fulfillment; 3DS flow crashed; refund issued multiple physical refunds — **do not cut over**, fix the defect, re-run shakedown from step 1 |
| `fail-nonblocking` | Notification latency exceeded target; non-critical webhook handler logged a warning; reconciliation report format changed — log to issue tracker with full reproduction context. Cutover may proceed with explicit sign-off |
| `inconclusive` | Stripe CLI could not connect; Test Clock unavailable; database snapshot stale — adjust environment and re-run the specific validation |

### Required Artifacts

- Execution log — full timestamped log of every Stripe API call with request ID, every webhook delivery with event ID and signature verification result, every handler invocation, every database mutation during the shakedown.
- Result summary — pass/fail classification per validation category with the specific Stripe request IDs and event IDs that drove each classification.
- Issue list — every anomaly observed, classified blocking/non-blocking/deferred, with the reproduction PaymentIntent ID, event ID, database state.
- Environment snapshot — Stripe API version pinned at shakedown time, `stripe-node` (or equivalent) version, webhook endpoint URL, webhook signing secret fingerprint (not the secret itself), database schema version, application commit SHA.

### Anti-Patterns

- Skipping shakedown because a change "only touched the webhook router" or "only updated the refund reason string". Changes that touch Stripe integration boundaries always warrant shakedown.
- Treating shakedown as a comprehensive test suite with dozens of assertions per card type.
- Running the shakedown against `stripe-mock`, a recorded fixture, or an in-memory stub. **Mocks hide integration faults.**
- Running the shakedown against live keys or live webhooks to "test in production". **Shakedown is test mode only.** Live-mode validation is a separate, bounded smoke test with explicit authorization.
- Tuning webhook retry windows, rewriting the dispatcher, or rebalancing idempotency cache TTL while the shakedown is running.
- Declaring shakedown passed without preserving the execution log, result summary, issue list, environment snapshot.

### Reference Happy-Path Harness

```javascript
// stripe-shakedown.js — test-mode round-trip validator
// Usage: node stripe-shakedown.js (runs against STRIPE_SECRET_KEY_TEST and STRIPE_WEBHOOK_SECRET_TEST)
import Stripe from 'stripe';
import { strict as assert } from 'node:assert';

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY_TEST, {
    apiVersion: '2024-12-18',
    maxNetworkRetries: 2,
});

async function runShakedown() {
    // 1. Auth sanity: reject if we accidentally loaded a live key
    const account = await stripe.accounts.retrieve();
    assert.equal(account.charges_enabled || account.details_submitted, true);
    const balance = await stripe.balance.retrieve();
    assert.equal(balance.livemode, false, 'shakedown refuses to run against live mode');

    // 2. Deterministic idempotency key from shakedown run ID
    const runId = process.env.SHAKEDOWN_RUN_ID;
    const idempotencyKey = `shakedown:pi:${runId}`;

    // 3. Happy path: PaymentIntent with 4242 test card via PaymentMethod
    const pm = await stripe.paymentMethods.create({
        type: 'card',
        card: { token: 'tok_visa' },
    });
    const pi = await stripe.paymentIntents.create(
        {
            amount: 100,
            currency: 'usd',
            payment_method: pm.id,
            confirm: true,
            automatic_payment_methods: { enabled: true, allow_redirects: 'never' },
            metadata: { shakedown_run_id: runId, category: 'happy_path' },
        },
        { idempotencyKey },
    );
    assert.equal(pi.status, 'succeeded', `expected succeeded, got ${pi.status}`);

    // 4. Idempotency dedup: retry same key, assert same PI ID returned
    const piRetry = await stripe.paymentIntents.create(
        {
            amount: 100,
            currency: 'usd',
            payment_method: pm.id,
            confirm: true,
            automatic_payment_methods: { enabled: true, allow_redirects: 'never' },
            metadata: { shakedown_run_id: runId, category: 'happy_path' },
        },
        { idempotencyKey },
    );
    assert.equal(piRetry.id, pi.id, 'idempotency key must return original PaymentIntent');

    // 5. Refund round-trip with its own deterministic key
    const refund = await stripe.refunds.create(
        { payment_intent: pi.id, metadata: { shakedown_run_id: runId } },
        { idempotencyKey: `shakedown:refund:${runId}` },
    );
    assert.equal(refund.status, 'succeeded');

    // 6. Balance transaction reconciliation
    const chargeId = typeof pi.latest_charge === 'string' ? pi.latest_charge : pi.latest_charge?.id;
    const charge = await stripe.charges.retrieve(chargeId, { expand: ['balance_transaction'] });
    assert.ok(charge.balance_transaction, 'balance_transaction required for ledger reconciliation');

    return {
        runId,
        paymentIntentId: pi.id,
        refundId: refund.id,
        balanceTransactionId: typeof charge.balance_transaction === 'string'
            ? charge.balance_transaction
            : charge.balance_transaction.id,
        classification: 'pass',
    };
}

runShakedown()
    .then((result) => {
        console.log(JSON.stringify({ shakedown: 'stripe', ...result }, null, 2));
        process.exit(0);
    })
    .catch((err) => {
        console.error(JSON.stringify({ shakedown: 'stripe', classification: 'fail-blocking', error: String(err) }, null, 2));
        process.exit(1);
    });
```

---
[Back to Overview](./OVERVIEW.md)
