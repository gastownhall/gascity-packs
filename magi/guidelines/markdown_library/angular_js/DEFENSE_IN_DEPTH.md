# Defense in Depth

Multiple, independent layers protect AngularJS legacy code from single failures.

### Independent Layers of Defense

1. **`ng-strict-di`**: Enabled at bootstrap to catch missing annotations.
2. **Lint**: ESLint/JSHint to prevent code rot.
3. **Karma units**: Covering controllers, services, and filters.
4. **End-to-end tests**: Catching digest-cycle bugs and routing failures.
5. **Minification validation**: Smoke-testing the production bundle.
6. **Production telemetry**: Monitoring error rates in deployment.
7. **Shakedown**: Integration validation against the real backend (§18).

### The Rule of Three — Majority Wins

- **One is a claim**: Source builds working locally.
- **Two is a tie**: Units pass but minified smoke fails.
- **Three is a quorum**: Lint + Units + Minified Smoke. **Majority MUST agree.**

**Intent: No single check, person, or tool is trusted as the sole safeguard.**

---
[Back to Overview](./OVERVIEW.md)
