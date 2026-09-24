
Read workflow root metadata, including `gc.github.review_report_path`,
`gc.github.comment_path`, `gc.github.review_outcome`, and `gc.github.post_mode`.
If `post_mode` {{post_mode}} is not `human_gate`, close this step as a no-op
gate with metadata `gc.github.public_comment_gate=not_required`.

In `headless` interaction mode ({{interaction_mode}} at launch), never wait on
a human: the snapshot compatibility gate blocks `human_gate` post mode for
headless runs, so reaching this step with both set means the gate was skipped.
Stop blocked with a machine-readable `gc.blocked_reason` instead of waiting.

If `post_mode` is `human_gate`, send the rendered review report and comment to
the human gate using the passive wait + mail pattern. This is not a
timeout-driven task.

1. Before waiting, update workflow root metadata with:
   - `gc.github.public_comment_gate=waiting-human`
   - `gc.github.public_comment_gate_bead_id=<this bead id>`
   - preserve any existing `gc.github.public_comment_gate_mail_sent=true`
2. Park the current session so idle handling does not recycle it while the
   human decides:
   ```bash
   SESSION_TARGET="${GC_SESSION_ID:-${GC_SESSION_NAME:-}}"
   SESSION_ATTACH="${GC_SESSION_NAME:-$SESSION_TARGET}"
   WAIT_NOTE="Waiting for human approval of GitHub PR review comment on bead $GC_BEAD_ID."
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
   `gc.github.public_comment_gate_mail_sent=true`, send exactly one mail with
   `gc mail send human ...`. Include the review report path, rendered comment
   path, workflow root id, this bead id, PR URL, and requested response
   options: approve, request changes, or reject. After sending, update workflow
   root metadata with `gc.github.public_comment_gate_mail_sent=true` and
   `gc.github.public_comment_gate_mail_to=human`.
4. Wait for explicit human feedback from the active session or mail thread. If
   the session idles, detaches, or restarts before the human responds, do not
   close this bead. A resumed worker must read the gate metadata and continue
   waiting from this gate.

Record exactly one terminal workflow-root metadata value after explicit human
feedback: `gc.github.public_comment_gate=approved`, `rejected`, or
`revision_requested`. Use `approved` only after explicit human approval,
`revision_requested` when the comment must be revised before posting, and
`rejected` when the comment must not be posted. Close fail only for explicit
rejection or abort, not for silence.
