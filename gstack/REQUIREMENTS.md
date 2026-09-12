# Gstack Lite Contract

- The pack root exposes skills only: no active `agents/`, `commands/`, or
  `formulas/` directories.
- `gstack-lite` is the default end-to-end delivery skill.
- The persistent Mayor remains Sol/high; explicit research and planning
  deliverables route to a persistent, attachable `gc.research-planner`
  conversation on the Sol/max `sol-research` provider by default; raw
  `--no-formula` beads are background-only.
- Interactive planning autostarts from the submitted brief, makes concrete
  kickoff progress, and emits an exact structured `READY_FOR_ATTACH` safe
  checkpoint. The Mayor queues autonomous continuation before exposing the
  attach command; attachment steers work but never starts or resumes it.
- The research-planner role is a singleton in every current rig; the audit
  rejects a new rig until it receives the same provider binding and cap.
- Every user-facing research engagement publishes an HTML/CSS bundle under the
  rig's reports namespace, registers an active library card, and verifies its
  live tailnet URL before completion.
- One bead has one implementation owner and one immutable source-head lease.
- Repository-native checks precede model review; a green baseline may be
  inherited only when bound to the same immutable head and check definition.
- The same checked immutable candidate is exposed to required CI, configured
  external PR review bots, and one different-family review for material changes.
  Bounded timeout/unavailable results are explicit.
- Findings are deduplicated in one exact-head artifact before the single repair
  allowance begins. All applicable surfaces evaluate the exact repaired head, and
  only a blocking consolidated re-review fails upward; safety always blocks.
- At most one repair owner may write after consolidated review. The prior owner
  must be drain-acknowledged or forcibly closed before reassignment.
- Rejected branches remain durably reachable with their exact commit, diff, and
  evidence until an approved successor carries them. Rescue carries work
  forward by default; rebuild from protected main requires a recorded
  architecture, provenance, or security reason.
- Protected publication, deployment, and a behavior canary remain distinct
  terminal states.
- Retired delivery graphs under `../deprecated/` are historical artifacts only
  and must not appear in the active city catalog.
- Final accounting records wall clock, provider lanes, queue time, checks,
  review, repair, deployment, rejected attempts, and human intervention.
- Comparable terminal accounting uses the versioned `gc.delivery/v1` metrics
  object on durable product beads. Deterministic rollups exclude ephemeral and
  control-plane churn and report field-level telemetry coverage.
- Operational health is a separate snapshot of supported `gc doctor --json`
  output. Advisory warnings do not become universal delivery blockers.

Run the contract checks from the repository root:

```sh
python3 -m pytest tests/test_gstack_lite_pack_contract.py tests/test_gstack_review_contract.py -q
python3 gstack/skills/gstack-lite/scripts/audit_city.py --city /path/to/city
```
