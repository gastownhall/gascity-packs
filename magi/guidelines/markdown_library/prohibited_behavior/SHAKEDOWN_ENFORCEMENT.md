# Shakedown Enforcement

Shakedown is the **first controlled end-to-end execution** of a system, change, or fix against real integration boundaries — real services, real databases, real browsers, real infrastructure. It is NOT a test suite, NOT a unit test, NOT an optional validation step. It is the only phase that exercises the seams the type checker and unit tests cannot see. The following six rules are enforced with the same zero-tolerance posture as the 23 core rules above.

## 24. Never Skip Shakedown After Integration-Boundary Changes

Any change that touches an integration boundary — service-to-service call, database schema, message contract, API surface, SDK public method, build artifact layout, deployment target, runtime version — **REQUIRES a shakedown** before the change is declared complete. "Small" changes that cross integration boundaries produce the most dangerous failures precisely because they are underestimated.

**PROHIBITED:**
- Skipping shakedown because the change "looks small"
- Skipping shakedown after an API signature change
- Skipping shakedown after a dependency upgrade that touches serialization, transport, or the reconciler
- Skipping shakedown after infrastructure or base image changes
- Skipping shakedown after a production hotfix

**REQUIRED:**
- Run shakedown after every integration-boundary change
- Run shakedown after every dependency upgrade that crosses a trust or transport seam
- Run shakedown after every runtime, base image, or infrastructure change
- Run shakedown after every repair that followed a systemic failure

**Rationale:** Integration failures do not announce themselves in unit tests. Shakedown is the only validation phase that exercises the real seams.

| Type | Scenario | Result |
|:-----|:---------|:-------|
| Incorrect | Developer bumps the HTTP client a single patch version and deploys without shakedown because "it compiled". | REJECTED — integration-boundary change requires shakedown |
| Correct | Developer bumps the HTTP client, runs the shakedown harness against staging, confirms the round-trip path, records the artifact set, then deploys. | Accepted |

## 25. Never Treat Shakedown as a Comprehensive Test Suite

Shakedown exercises a small, fixed set of representative cases with known-good inputs. Expanding shakedown into dozens of assertions converts it into slow, duplicated coverage that belongs in the unit or integration test layer.

**PROHIBITED:**
- Adding dozens of assertions to a shakedown run
- Copying unit-test cases into shakedown
- Running the full regression suite as shakedown
- Treating a passing test suite as a completed shakedown

**REQUIRED:**
- Keep shakedown to the minimum representative path set for the domain
- Move behavioral assertions into the test suite, not shakedown
- Run shakedown as a distinct phase from unit, integration, and E2E testing

**Rationale:** Shakedown answers "does the integrated system run?". Testing answers "does it behave correctly?". Conflating the two destroys both.

## 26. Never Run Shakedown in a Mocked or Non-Representative Environment

Shakedown exists to detect integration faults that live only in real seams. A shakedown performed against mocked services, in-memory databases, jsdom browsers, or dev-mode bundlers detects nothing that matters.

**PROHIBITED:**
- Running shakedown with MSW, nock, or any fetch mock
- Running shakedown against `sqlite-in-memory` when production is Postgres
- Running shakedown in jsdom instead of a real browser
- Running shakedown against a dev-mode bundler or hot-reload server
- Stubbing any seam shakedown is supposed to exercise

**REQUIRED:**
- Run shakedown against a real runtime at the exact pinned production version
- Run shakedown against a real backend with seeded known-good data
- Run shakedown against a real browser when the domain has a browser surface
- Run shakedown against the production-mode build artifact, not the dev-mode server

**Rationale:** A mocked seam is a hidden seam. The purpose of shakedown is to expose what the type checker and unit tests cannot.

| Type | Scenario | Result |
|:-----|:---------|:-------|
| Incorrect | CI "shakedown" job runs the app in jsdom with MSW intercepting fetch. | REJECTED — that is an integration unit test, not a shakedown |
| Correct | CI shakedown job boots the production build against a real staging backend in real Chromium. | Accepted |

## 27. Never Optimize During Shakedown

Shakedown validates correctness. Optimization introduces new changes that themselves require shakedown. Mixing optimization into the validation phase invalidates the validation.

**PROHIBITED:**
- Tuning bundle size during shakedown
- Refactoring hot paths while shakedown is running
- Adjusting retry policies to "make shakedown pass"
- Treating shakedown as a profiling session

**REQUIRED:**
- Log performance anomalies to the issue tracker and move on
- Complete shakedown classification before any optimization work begins
- Run a fresh shakedown after any optimization that touches an integration seam

**Rationale:** Optimization during validation is an invalidation. The only acceptable output of shakedown is a classification (`pass` / `fail-blocking` / `fail-nonblocking` / `inconclusive`), never a code change.

## 28. Never Deploy Without a Recorded Shakedown Artifact Set

A shakedown without artifacts is a shakedown that never happened. Every deployment must have a retrievable artifact set:

| Artifact | Purpose |
|:---------|:--------|
| Execution log | Full timestamped record of the run |
| Result summary | Per-category pass/fail breakdown |
| Issue list | Anomalies with classification and reproduction context |
| Environment snapshot | Runtime versions, lockfile hash, infrastructure state |

**PROHIBITED:**
- Deploying without an execution log
- Deploying without a result summary
- Deploying without an environment snapshot
- Deploying without the issue list
- Relying on memory of a shakedown run

**REQUIRED:**
- Capture the full timestamped execution log
- Capture the per-category result summary
- Capture the issue list with classification and reproduction context
- Capture the environment snapshot
- Store the artifact set alongside the build in a retrievable location

**Rationale:** The artifact set is the only proof the shakedown occurred. Without it, the validation baseline is unrecoverable and drift detection is impossible.

## 29. Never Declare a System Ready With a Stale Shakedown

A shakedown validates the **exact code, dependencies, and infrastructure** present at the moment it ran. Any drift — a dependency bump, an infrastructure change, a config update — invalidates the prior shakedown. "Ready" means the most recent shakedown matches the current baseline.

**PROHIBITED:**
- Declaring ready with a shakedown predating the current lockfile
- Declaring ready with a shakedown predating the current infrastructure state
- Declaring ready with a shakedown predating the current API contract
- Declaring ready after a hotfix without re-running shakedown
- Declaring ready on a system that has been dormant while its environment drifted

**REQUIRED:**
- Diff the current environment against the most recent shakedown snapshot before declaring ready
- Re-run shakedown on any drift detected in runtime, dependencies, or infrastructure
- Re-run shakedown after extended dormancy
- Treat the shakedown snapshot as the single source of truth for the validated baseline

**Rationale:** Shakedown validates a specific point in time. Time moves. Drift is constant. A stale shakedown is a fictional guarantee.

| Type | Scenario | Result |
|:-----|:---------|:-------|
| Incorrect | System passed shakedown two weeks ago. Three dependency upgrades and a base image bump later, the developer cites the old shakedown as proof of readiness. | REJECTED — baseline no longer matches current state |
| Correct | Developer diffs current lockfile and base image against the last shakedown snapshot, detects drift, re-runs shakedown, records a fresh artifact set, then declares ready. | Accepted |

---
[Back to Overview](./OVERVIEW.md)
