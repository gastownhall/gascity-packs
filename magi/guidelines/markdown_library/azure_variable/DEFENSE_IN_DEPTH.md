# Defense in Depth

Multiple, independent layers protect Azure CLI usage and parameterization from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Turnkey script wrappers** — Every `az` command MUST live inside a turnkey script in `.utilities/.azure/`. Discrete `az` commands at the prompt are forbidden.
2. **Input validation** — Every script parameter MUST be validated (subscription, resource-group, location, name pattern) before any `az` call runs.
3. **Dry-run flag** — Every mutating script MUST support `--dry-run` / `--what-if` so the operator sees the planned action.
4. **Audit log of runs** — Each script run MUST append a timestamped record (who, what, args, exit code) to a project-local log.
5. **Idempotency** — Re-running the same script MUST converge; `az group create` + `az resource update` style commands MUST NOT error on existing state.
6. **Least-privilege service principals** — Scripts that run unattended MUST authenticate with a scoped service principal, not a human user.
7. **Policy and resource locks** — Resource locks and Azure Policy MUST exist as independent guardrails; the script is the first defense, the policy is the second.
8. **Variable-restructure shakedown** — §18 covers rename paths the lint and what-if cannot fully validate.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — A successful `az` exit code is one signal. The resource may exist in a partial state.
- **Two is a tie** — Exit 0 + the script's own post-condition check disagreeing means the command lied or the resource is still provisioning; treat as failure until reconciled.
- **Three is a quorum** — Script exit code + post-condition `az show` / `az resource list` + Azure Activity Log entry form the triple. **All three MUST agree** before declaring the operation done.

Example: `az vm create` returning 0 while the VM is in `Failed` provisioning state — only the post-condition show + activity log catches it.

---
[Back to Overview](./OVERVIEW.md)
