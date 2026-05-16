# Deployment Strategies and Gating

### Production Gate Requirements

Production deployments require passing **all** upstream quality gates:
- lint
- test
- build
- security scan
- artifact signing
- staging deployment
- staging smoke tests

**No gate is optional.** Manual override of failed gates requires documented justification and post-deployment review.

### Human Approval for Production

Production deployments require explicit human approval from a designated set of approvers. The approval must be recorded in the pipeline audit trail with the approver's identity and timestamp.

### Progressive Deployment Strategies

| Strategy | Description |
|:---------|:------------|
| Canary | Route 5-10% of traffic to the new version, monitor, then expand |
| Blue-Green | Deploy to inactive environment, switch traffic after validation |
| Rolling | Update instances sequentially with health check gates between batches |
| Big-bang | Replace all instances simultaneously — **highest risk; reserve for stateless services with instant rollback** |

### Smoke Tests

Run smoke tests automatically after each deployment stage. Verify critical paths:
- Health endpoints return 200
- Authentication works
- Core API endpoints respond
- Key UI flows render

Smoke test failure triggers automatic rollback in canary/progressive deployments or alerts the on-call engineer for immediate investigation.

### Deployment Windows

Define approved hours for routine deployments (e.g., Tuesday-Thursday, 10:00-16:00 local time). Deployments outside windows require explicit justification (hotfix). **Deploying at 5 PM Friday introduces risk with minimal team availability for incident response.**

### Promote, Don't Rebuild

Deploy the **same artifact** to all environments. **Do not rebuild for production.** Rebuilding introduces variance: a dependency that resolved to version X during CI may resolve to version Y during a production rebuild.

---
[Back to Overview](./OVERVIEW.md)
