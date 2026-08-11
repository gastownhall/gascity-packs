Use the built-in Gas City `design-review` flow.

Run a plan review against the implementation plan. Treat required changes as blockers for decomposition; update the plan or capture the unresolved findings before closing this step.

Include a lightweight implementation readiness pass before decomposition:

- requirements traceability: every major plan task maps to acceptance criteria
- task boundaries: each task can become a clear implementation bead
- test commands: the plan names the focused proof commands or test strategy
- risk: risky files, migrations, public interfaces, and rollback concerns are
  explicit enough for an implementer

If you write a plan-readiness note, record it on the workflow root as
`gc.build.plan_review_report_path=<path>`. Do not write or overwrite
`gc.build.review_report_path`; that key is reserved for the later
build-basic implementation review artifact.

Honor interaction_mode {{interaction_mode}} at the plan-review verdict.

In `autonomous` mode, record the review verdict and proceed without waiting on
a human. In `headless` mode, never ask questions and never wait on a human; if
the work item strictly requires human design approval, stop blocked with a
machine-readable `gc.blocked_reason` (for example
`interactive-approval-required:headless`) instead of waiting.

In `interactive` mode, do not close this stage on your own verdict. Send the
plan-review verdict to the human gate using the passive wait + mail pattern.
This is not a timeout-driven task.

1. Before waiting, update workflow root metadata with:
   - `gc.build.plan_review_gate=waiting-human`
   - `gc.build.plan_review_gate_bead_id=<this bead id>`
   - preserve any existing `gc.build.plan_review_gate_mail_sent=true`
2. Park the current session so idle handling does not recycle it while the
   human decides:
   ```bash
   SESSION_TARGET="${GC_SESSION_ID:-${GC_SESSION_NAME:-}}"
   SESSION_ATTACH="${GC_SESSION_NAME:-$SESSION_TARGET}"
   WAIT_NOTE="Waiting for human approval of the implementation plan on bead $GC_BEAD_ID."
   if [ -n "$SESSION_ATTACH" ]; then
     WAIT_NOTE="$WAIT_NOTE Resume with: gc session attach $SESSION_ATTACH"
   fi
   if [ -n "$SESSION_TARGET" ] && ! gc wait list --session "$SESSION_TARGET" | grep -Fq "$WAIT_NOTE"; then
     gc session wait "$SESSION_TARGET" \
       --sleep \
       --on-beads "$GC_BEAD_ID" \
       --note "$WAIT_NOTE"
   fi
   ```
3. If workflow root metadata does not already have
   `gc.build.plan_review_gate_mail_sent=true`, send exactly one mail with
   `gc mail send human ...`. Include the plan path, the plan-review verdict and
   findings (or `gc.build.plan_review_report_path` when written), the workflow
   root id, this bead id, and the requested response options: approve, request
   changes, or reject. After sending, update workflow root metadata with
   `gc.build.plan_review_gate_mail_sent=true` and
   `gc.build.plan_review_gate_mail_to=human`.
4. Wait for explicit human feedback from the active session or mail thread. If
   the session idles, detaches, or restarts before the human responds, do not
   close this bead. A resumed worker must read the gate metadata and continue
   waiting from this gate.

Record exactly one terminal workflow-root metadata value after explicit human
feedback: `gc.build.plan_review_gate=approved`, `rejected`, or
`revision_requested`. Use `approved` only after explicit human approval, and
`rejected` when the build must not proceed. Close fail only for explicit
rejection or abort, not for silence.

`revision_requested` is NOT terminal — no downstream stage loops back to the
plan, so the revision loop lives here. On `revision_requested`: revise the
plan in place per the human's findings (record what changed and why in the
plan-review notes), re-review it, reset
`gc.build.plan_review_gate=waiting-human`, clear
`gc.build.plan_review_gate_mail_sent` so the human is notified again, and
repeat the gate wait. In `interactive` mode, close pass ONLY after
`gc.build.plan_review_gate=approved` is recorded.
