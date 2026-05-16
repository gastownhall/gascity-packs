# Testing

### Test Mode

Stripe's test mode provides a complete simulation of the API using test keys:

- **No real payments**, no card networks, no real money movement.
- Use test mode for all development, staging, CI/CD, and automated testing.

**Test card numbers:**

| Card | Outcome |
|:-----|:--------|
| `4242424242424242` | Successful charge |
| `4000000000000002` | Generic decline |
| `4000002500003155` | Requires 3D Secure |
| `4000000000009995` | Insufficient funds |

### Webhook Testing

```bash
# Forward live test-mode events to local server with valid signatures
stripe listen --forward-to localhost:3000/api/webhooks/stripe

# Trigger specific events on demand
stripe trigger payment_intent.succeeded
```

For automated tests, construct webhook events with `stripe.webhooks.generateTestHeaderString()` to create valid signatures against a known signing secret. Test the full handler path: signature verification, deduplication, business logic, response.

### Integration Testing Patterns

- Integration tests create real Stripe test-mode objects (Customers, PaymentIntents, Subscriptions) and verify end-to-end behavior.
- **Clean up test objects after tests** (delete test customers, cancel test subscriptions) to prevent test data accumulation.
- Use separate Stripe test accounts for CI to isolate test data from developer test accounts.
- **Mock Stripe in unit tests** using SDK mock capabilities or `stripe-mock`. Reserve real API calls for integration tests.

### Test Clocks for Subscriptions

Stripe **Test Clocks** simulate the passage of time for subscription testing:

- Create a test clock, attach customers to it, advance the clock to trigger billing cycles, trial endings, dunning sequences without waiting days or weeks.
- Use test clocks in staging and CI to verify subscription lifecycle logic: trial-to-paid conversion, renewal billing, payment failure sequences, cancellation behavior.
- **Test clocks are essential for subscription-heavy integrations** — manually testing billing cycles in real time is not viable.

---
[Back to Overview](./OVERVIEW.md)
