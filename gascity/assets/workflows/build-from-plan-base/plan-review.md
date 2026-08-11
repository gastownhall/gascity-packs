This is the `build-from-plan-base` plan-review stage.

Review the implementation plan before decomposition. The verdict must map to
approved, questions, changes_required, or blocked, and it must honor
interaction_mode {{interaction_mode}}.

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
   findings, the workflow root id, this bead id, and the requested response
   options: approve, request changes, or reject. After sending, update workflow
   root metadata with `gc.build.plan_review_gate_mail_sent=true` and
   `gc.build.plan_review_gate_mail_to=human`.
4. Wait for explicit human feedback from the active session or mail thread. If
   the session idles, detaches, or restarts before the human responds, do not
   close this bead. A resumed worker must read the gate metadata and continue
   waiting from this gate.

Record exactly one terminal workflow-root metadata value after explicit human
feedback: `gc.build.plan_review_gate=approved`, `rejected`, or
`revision_requested`. Use `approved` only after explicit human approval, and
`rejected` when the continuation must not proceed. Close fail only for
explicit rejection or abort, not for silence.

`revision_requested` is NOT terminal for this stage — there is no downstream
loopback (the sole successor, prepare-decompose, requires an approved plan),
so the revision loop lives here. On `revision_requested`:

1. Revise the plan artifact in place per the human's findings and record the
   revision (what changed and why) in the plan-review artifact under a dated
   "Human revision round" heading.
2. Re-review the revised plan and update the verdict.
3. Reset the gate for the next round: set
   `gc.build.plan_review_gate=waiting-human` and clear
   `gc.build.plan_review_gate_mail_sent` so the human is notified again.
4. Repeat the gate wait until the human answers `approved` or `rejected`.

Write the plan-review artifact to `{{plan_review_path}}` when supplied;
otherwise write it under `{{artifact_root}}`. In `interactive` mode, close
pass ONLY after `gc.build.plan_review_gate=approved` is recorded — never with
a changes-required artifact, which downstream would either stall on or
mistake for an approved plan. In `autonomous`/`headless` mode, close after an
approved or equivalent pass verdict is recorded, or after a
blocked/changes-required verdict is recorded with a concrete reason.
