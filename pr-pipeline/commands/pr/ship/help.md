Run the pre-push gate on the current branch — simplify, iterate
self-review until clean, run mechanical contributor checks, produce a
combined readiness report. **STOPS at the report.** Does NOT push, does
NOT open a PR.

The point: catch structural and correctness defects before the
maintainer's review cycle, so the PR lands with zero or near-zero
review comments.

This dispatches a coding agent to a rig with the `mol-pr-ship` formula.
The agent CAN modify files in stages 1-2 (simplify + review fixes); all
other stages are read-only. The push and PR-open decisions remain with
the caller — this formula gates, doesn't ship.

Usage:
  gc <binding> pr ship [flags]

Flags:
  --branch <name>     Branch to gate (defaults to current branch).
                      Refuses to ship from main / default branch.
  --skip-simplify     Skip Stage 1 (simplify) — useful when the diff
                      is already clean or simplify is disruptive.
  --rig <name>        Rig to ship inside (defaults to $GC_RIG).
  --agent <name>      Worker agent name (default: "polecat").

Stages:
  1. Simplify         Remove dead code, consolidate duplicates.
                      Reverted if it breaks the build.
  2. Self-review      Iterate against the 11-category scorecard until
                      no blockers/majors remain. Capped at 3 iterations.
  3. Contributor      Mechanical gates — build, vet/lint, tests, docs.
                      Read-only.
  4. Report + STOP    Combined readiness report. Verdict: READY | BLOCKED.

Examples:
  gc <binding> pr ship --rig api-server
  gc <binding> pr ship --skip-simplify --rig api-server
  gc <binding> pr ship --branch fix/some-feature --rig api-server

Direct sling (skip this command):
  gc sling api-server/polecat mol-pr-ship --formula --var branch="" \
      --var skip_simplify=false

Output:
  Report at <repo-root>/.gc/pr-pipeline/ship/<branch>.md
  Root-bead notes record `readiness:` (READY | BLOCKED) and `blockers:`.

After a READY verdict:
  Push to your fork and open a PR — those are explicit caller actions
  this formula will never perform.
