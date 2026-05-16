# Defense in Depth

Multiple, independent layers protect Bicep / Azure IaC from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Bicep build and lint** — `bicep build` and `bicep lint` MUST pass; warnings MUST be treated as errors in CI.
2. **What-if deployment** — `az deployment what-if` MUST run before every deploy; the diff MUST be reviewed.
3. **Parameter validation** — Parameter decorators (`@allowed`, `@minLength`, `@minValue`) MUST constrain inputs at the template level.
4. **Policy as code** — Azure Policy MUST enforce compliance independently of the template (so a misconfigured template still does NOT deploy a non-compliant resource).
5. **Drift detection** — Periodic what-if (or Terraform-style drift checks) MUST flag manual portal changes that diverged from the template.
6. **Cost estimation** — Cost diffs MUST be reported on every PR (Infracost or `az cost` analysis) so a typo does NOT bankrupt the subscription.
7. **Rollback plan** — Every deployment MUST have a documented rollback (prior template version pinned in source control).
8. **Post-deployment shakedown** — §19 covers wiring/identity/RBAC paths the template-time checks cannot.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — A template that `bicep build` accepts is one signal. It tells you the syntax compiles, NOT that ARM accepts it.
- **Two is a tie** — `what-if` showing the expected diff but ARM rejecting at deploy time is the API-vs-template dissent. **ARM wins.**
- **Three is a quorum** — `bicep build` + `what-if` + policy/drift check form the triple. All three MUST agree before any deployment to a shared subscription.

Example: a what-if that shows a benign change still triggers a soft-locked resource recreation; the policy engine flagging it is the third voter that prevents data loss.

---
[Back to Overview](./OVERVIEW.md)
