{{ define "gstack-lite-policy" -}}
# Gstack Lite Delivery Policy

For ordinary software work, use the lightweight path: one durable bead, one
implementation owner, repository-native checks, one consolidated exact-head
review round, at most one repair cycle with consolidated exact-repaired-head
re-review, protected publication, deployment, smoke verification, and concise
wall-clock/rework accounting.

- Keep the persistent Mayor on Sol/high for responsive intake and final
  adjudication. For substantial research or planning, create a persistent,
  attachable `gc.research-planner` session on the `sol-research` Sol/max
  provider, seed an autostart brief with `gc session submit`, and verify an
  exact assistant `READY_FOR_ATTACH` safe-checkpoint entry. Immediately queue
  autonomous continuation before returning its `gc session attach` command;
  attachment must never start or resume the research. Suspend it between planning
  conversations and close it only after approved artifacts and the live report
  are complete. Use `gc sling ... --no-formula` only for explicitly background
  work. Cap the lane at one active session in the city and every rig.
- Every user-facing research engagement must publish an HTML/CSS report under
  `/home/nvidia/gascity/reports/<rig>/<slug>/`, add it to the active reports
  library, and verify the live tailnet URL before completion.
- Never launch a retired delivery graph. Do not mention retired workflow names
  to the user unless they ask about history or a live violation is detected.
- Add gstack planning, design, QA, security, migration, documentation, or
  release skills only when the changed surface warrants that gate.
- Keep at most two independent implementation writers and one reviewer.
  Escalation replaces a writer; it does not add concurrency.
- Record one exclusive write lease per bead/branch/worktree. Before rescue or
  repair, drain and verify the prior owner is stopped; reject late commits from
  a revoked lease.
- Record a repository-defined delivery lane and concrete risk reasons. A
  claimed, leased bead authorizes ordinary repository edits, checks, and review
  without repeated approval mail; external publication, production cutover,
  credential use, service restart, and other irreversible operations retain
  their explicit authority gates.
- Emit concise owner-visible status only at start, external wait, material
  risk/ETA change, decision gate, and terminal outcome. Use nudge/status
  channels for routine updates, not permanent mail.
- After checks, expose the same immutable candidate to required CI, configured
  external PR bots, and one different-family reviewer for material changes. A
  draft/non-mergeable PR gathers feedback but grants no merge authority. Require
  SHA-bound run/comment evidence that each bot ran; a configuration skip is not
  a timeout, so use an explicit trigger or merge-blocked ready-for-review PR.
- Wait for every applicable surface or record a bounded timeout/unavailable
  result; aggregate and deduplicate one exact-SHA artifact before repair starts,
  including reviewer session, surface verdicts, finding class/severity/blocking
  reason, location, evidence, and required fix.
- Use one focused repair, rerun affected checks, and require every applicable
  surface to review the exact repaired head. Only a blocking consolidated
  re-review fails upward; any safety finding always blocks merge. Apply the same
  bounded-result rule to re-review. An unavailable required surface blocks merge
  unless repository protection explicitly exempts it and that is recorded.
- Submit a repaired head to the same live reviewer session with
  `gc session submit <reviewer-session> ... --intent follow_up`; only a recorded
  unavailable reviewer permits replacement. A narrowly authorized second safety
  repair remains on the same bead, branch, worktree, and lease.
- Benchmarks are isolated experiments: use an experiment root, `bench/` branch,
  worktree, dataset, and result path; never consume a product delivery lease or
  change delivery metrics.
- Preserve rejected branches until exact commits, diffs, and evidence are
  durably reachable. Rescue carries the failed candidate forward by default;
  rebuild from protected
  `main` only for a recorded architecture, provenance, or security reason. A
  rescue lane must reproduce or edit within four minutes or return the evidence.
- Preserve one durable `main`. Delete the accepted branch after merge.
- “Implemented,” “merged,” and “verified in production” are distinct states.
  Continue until the user's requested terminal state is proven.
{{- end }}
