This is the build-basic starter review's human gate — an EXECUTABLE child
bead (the loop step itself is orchestrator-owned control and no worker ever
runs its description), sequenced after apply-review-findings so every loop
iteration ends with it.

Honor interaction_mode {{interaction_mode}}:

In `autonomous` mode, close immediately with `gc.outcome=pass` — the loop
concludes on the machine verdict alone. In `headless` mode, never ask questions and
never wait on a human; if human review approval is strictly
required, stop blocked with a machine-readable `gc.blocked_reason` (for
example `interactive-approval-required:headless`) instead of waiting.

In `interactive` mode, read the current `code_review.verdict` for this
attempt. If it is `iterate`, the machine loop is not done — close pass
without engaging the human; the implementation review check will schedule
the next iteration off the verdict. If it is `done`, engage the
passive wait + mail human gate (canonical mechanics in
`../build-base/interactive-human-gate.md`) with gate key
`gc.build.review_gate`. This is not a timeout-driven task.

1. Before waiting, update workflow root metadata with
   `gc.build.review_gate=waiting-human` and
   `gc.build.review_gate_bead_id=<this bead id>`; preserve any existing
   `gc.build.review_gate_mail_sent=true`.
2. Park the session (`gc session wait --sleep --on-beads "$GC_BEAD_ID"`)
   with a resume note, exactly as the canonical mechanics describe.
3. If `gc.build.review_gate_mail_sent=true` is not already set, send exactly
   one mail with `gc mail send human ...` carrying the starter review summary
   path, workflow root id, this bead id, and the response options (approve,
   request changes, reject); then set `gc.build.review_gate_mail_sent=true`
   and `gc.build.review_gate_mail_to=human`.
4. Wait for the explicit human verdict. Do not close this bead on idle,
   detach, or restart; a resumed worker re-reads the gate metadata and
   continues waiting.

Record exactly one workflow-root value after explicit human feedback:
`gc.build.review_gate=approved`, `rejected`, or `revision_requested`.

On `revision_requested`, before closing:

1. Persist the human findings to a dedicated file under the build artifact
   root (for example `<artifact_root>/human-review-findings-attempt-<n>.md`)
   and record it on the workflow root as
   `gc.build.human_findings_path=<path>`. The next attempt's synthesis and
   apply lanes consume that path as required fixes — appending to the old
   attempt's summary does NOT reach them.
2. Clear `gc.build.review_gate_mail_sent` on the workflow root so the next
   gate round notifies the human again.
3. Close this bead with `gc.outcome=pass`. The implementation review check
   reads `gc.build.review_gate=revision_requested` and schedules the next
   loop iteration — the gate metadata, not this bead staying open, drives
   the iteration.

On `approved`, close pass. On `rejected`, close fail with the human's
reason. Close fail only for explicit rejection or abort, never for silence.

Do not invoke provider-native subagents.
