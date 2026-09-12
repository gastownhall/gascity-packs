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
- After checks, expose the same immutable candidate to required CI, configured
  external PR bots, and one different-family reviewer for material changes. A
  draft/non-mergeable PR gathers feedback but grants no merge authority.
- Wait for every applicable surface or record a bounded timeout/unavailable
  result; aggregate and deduplicate one exact-SHA artifact before repair starts.
- Use one focused repair, rerun affected checks, and require every applicable
  surface to review the exact repaired head. Only a blocking consolidated
  re-review fails upward; any safety finding always blocks merge.
- Preserve rejected branches until exact commits, diffs, and evidence are
  durably reachable. Rescue carries the failed candidate forward by default;
  rebuild from protected
  `main` only for a recorded architecture, provenance, or security reason. A
  rescue lane must reproduce or edit within four minutes or return the evidence.
- “Implemented,” “merged,” and “verified in production” are distinct states.
  Continue until the user's requested terminal state is proven.
{{- end }}
