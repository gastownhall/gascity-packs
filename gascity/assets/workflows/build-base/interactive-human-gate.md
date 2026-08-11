Passive wait + mail human gate for build-family interactive checkpoints.

This is the canonical human-gate mechanic for `interaction_mode=interactive`
in the build-base family: the passive wait + mail pattern, ported from the
GitHub PR review `human-gate-comment` step. Stage prompts embed these
mechanics with a stage-specific gate key: `gc.build.plan_review_gate` for the plan-review
verdict and `gc.build.review_gate` for the implementation review loop
approval. This is not a timeout-driven task.

In `interactive` interaction mode, the stage must not close on its own
verdict: it parks the session, mails the human, and waits for the explicit
human verdict.

In `autonomous` interaction mode, skip this gate entirely: record the verdict
from the review evidence and proceed without waiting on a human.

In `headless` interaction mode, never ask questions and never wait on a
human. If the work item strictly requires human approval, stop blocked
with a machine-readable `gc.blocked_reason` (for example
`interactive-approval-required:headless`) instead of waiting.

Gate mechanics for `interactive` mode, with `<gate key>` standing in for the
stage-specific key:

1. Before waiting, update workflow root metadata with:
   - `<gate key>=waiting-human`
   - `<gate key>_bead_id=<this bead id>`
   - preserve any existing `<gate key>_mail_sent=true`
2. Park the current session so idle handling does not recycle it while the
   human decides:
   ```bash
   SESSION_TARGET="${GC_SESSION_ID:-${GC_SESSION_NAME:-}}"
   SESSION_ATTACH="${GC_SESSION_NAME:-$SESSION_TARGET}"
   WAIT_NOTE="Waiting for human review verdict on bead $GC_BEAD_ID."
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
3. If workflow root metadata does not already have `<gate key>_mail_sent=true`,
   send exactly one mail with `gc mail send human ...`. Include the artifact
   path under review, the verdict and findings so far, the workflow root id,
   this bead id, and the requested response options: approve, request changes,
   or reject. After sending, update workflow root metadata with
   `<gate key>_mail_sent=true` and `<gate key>_mail_to=human`.
4. Wait for explicit human feedback from the active session or mail thread. If
   the session idles, detaches, or restarts before the human responds, do not
   close this bead. A resumed worker must read the gate metadata and continue
   waiting from this gate.

Record exactly one terminal workflow-root metadata value after explicit human
feedback: `<gate key>=approved`, `rejected`, or `revision_requested`. Use
`approved` only after explicit human approval, `revision_requested` when the
artifact must be revised before the stage can pass, and `rejected` when the
work must not proceed. Close fail only for explicit rejection or abort, not
for silence.

`revision_requested` must actually produce another round — recording it and
closing pass would silently discard the human's findings. Two shapes, chosen
by the stage:

- Check-driven loop stages (the implementation review loop): persist the
  findings where the next iteration reads them, clear `<gate key>_mail_sent`,
  and close per contract — the stage's check reads
  `<gate key>=revision_requested` and schedules the next iteration.
- Single-stage gates with no downstream loopback (plan review): revise the
  artifact in place, re-review, reset `<gate key>=waiting-human`, clear
  `<gate key>_mail_sent`, and repeat the gate wait. Close pass only after
  `<gate key>=approved`.
