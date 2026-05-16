# Testing Strategy in CI

| Test Type | Trigger | Target Duration |
|:----------|:--------|:----------------|
| Unit tests | Every commit and PR | < 5 minutes |
| Integration tests | Every merge to main (minimum) | Variable |
| End-to-end tests | Before production promotion (critical path); post-deploy (full) | Longer |

### Unit Tests

The first automated quality gate. Must complete in under 5 minutes for rapid feedback. **Slow unit test suites indicate design problems** (excessive I/O, missing mocks, integration tests masquerading as unit tests).

### Integration Tests

Verify component interactions with real or realistic dependencies. Slower than unit tests but catch contract violations, schema mismatches, and configuration errors.

### End-to-End Tests

Verify the complete user-facing flow through the deployed system. Run the critical path E2E suite as a deployment gate. Run the full E2E suite post-deployment with alerting on failure.

### Test Result Format

Test results must be **machine-parseable** (JUnit XML, TAP, or JSON) and published as pipeline artifacts. Configure the CI platform to display test results in the PR/MR interface.

### Flaky Tests

Track and quarantine flaky tests. **A flaky test that passes on retry is not a passing test** — it is a test with intermittent failures that erodes confidence in the entire suite. Flaky tests must be flagged, tracked, and either fixed or removed within a defined SLA (e.g., 2 weeks). **Do not add automatic retry logic as a substitute for fixing flaky tests.**

### Coverage Floors

Enforce code coverage thresholds as a quality **gate**, not a metric to maximize. Set a floor (e.g., 80% line coverage) that prevents coverage from degrading. Require new code to meet the threshold. **Do not chase 100%** — the effort to cover the last 5% is disproportionate to its value and encourages meaningless tests.

---
[Back to Overview](./OVERVIEW.md)
