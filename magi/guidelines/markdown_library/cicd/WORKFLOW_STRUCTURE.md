# Workflow Structure and Organization

### Sequential Stage Gates

Organize pipelines into discrete stages with clear responsibilities:

```text
lint → test → build → scan → publish → deploy
```

Each stage gates the next. A failure in lint prevents test execution. A failure in test prevents build. **No stage executes unless all upstream stages succeed.**

### Parallelism Within Stages

Parallelize independent jobs within each stage. Unit tests, integration tests, and static analysis can run concurrently. Linting multiple languages runs concurrently. Parallel execution reduces total pipeline duration without sacrificing correctness.

### Reusable Templates

Extract reusable pipeline logic into shared templates, composite actions, or reusable workflows. Shared CI logic (build steps, deployment procedures, notification patterns) lives in a dedicated CI repository or shared workflow directory. Duplicated pipeline code across repositories drifts and diverges.

### Trigger Conditions

Define explicit triggers for every workflow:

| Trigger | Stages Run |
|:--------|:-----------|
| Push to `main` | Full pipeline |
| Pull request | lint, test, build (no deploy) |
| Tag creation | Release packaging and publishing |
| Schedule | Dependency updates, security scans |
| Manual | Hotfix deployments with required approvals |

### Path-Based Filtering

Skip irrelevant pipeline runs:
- Documentation-only changes do not trigger build and deploy stages
- Infrastructure changes do not trigger application test suites

Path filters reduce CI compute waste and queue congestion.

### Timeouts

**Set explicit timeouts on every job and step.** A hung build that runs 6 hours without a timeout consumes a runner, blocks the queue, and delays all subsequent pipelines:
- Job-level timeouts: 2-3× expected duration
- Step-level timeouts: for known-duration operations

### Concurrency Cancellation

Cancel in-progress runs when a new commit pushes to the same branch. Superseded runs produce artifacts for outdated code. Use concurrency groups (GitHub Actions: `concurrency`, GitLab CI: `resource_group`, or equivalent).

### DRY vs Readability

Keep pipeline configuration DRY via YAML anchors, matrix strategies, template inheritance, or composable workflow files. Repetitive step definitions across jobs indicate missing abstraction. **But prioritize readability over cleverness** — a pipeline that requires 20 minutes to understand is a pipeline that will be misconfigured.

---
[Back to Overview](./OVERVIEW.md)
