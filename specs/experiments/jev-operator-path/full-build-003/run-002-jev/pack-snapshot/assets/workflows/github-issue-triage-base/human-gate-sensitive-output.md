
Read workflow root metadata, including `gc.github.post_mode`,
`gc.github.triage_priority`, and `gc.github.triage_verdict`.

If `post_mode=human_gate`, priority is `p0`, or verdict is
`security_sensitive`, send the rendered triage report and proposed comment to
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
   WAIT_NOTE="Waiting for human approval of GitHub issue triage comment on bead $GC_BEAD_ID."
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
   `gc mail send human ...`. Include the triage report path, proposed comment
   path, workflow root id, this bead id, GitHub issue URL, and requested
   response options: approve, request changes, or reject. After sending, update
   workflow root metadata with `gc.github.public_comment_gate_mail_sent=true`
   and `gc.github.public_comment_gate_mail_to=human`.
4. Wait for explicit human feedback from the active session or mail thread. If
   the session idles, detaches, or restarts before the human responds, do not
   close this bead. A resumed worker must read the gate metadata and continue
   waiting from this gate.

Record exactly one terminal workflow-root metadata value after explicit human
feedback: `gc.github.public_comment_gate=approved`, `rejected`, or
`revision_requested`. Use `approved` only after explicit human approval,
`revision_requested` when the public comment must be revised before posting,
and `rejected` when the public comment must not be posted. Close fail only for
explicit rejection or abort, not for silence. If none of those conditions
applies, close this step as a no-op gate with metadata
`gc.github.public_comment_gate=not_required`.

This gate intentionally evaluates runtime triage metadata in the step body
rather than a static formula condition.
