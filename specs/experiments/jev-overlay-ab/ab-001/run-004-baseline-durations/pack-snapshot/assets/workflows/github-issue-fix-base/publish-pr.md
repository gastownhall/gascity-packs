
Only after build passes implementation, gap-analysis, and review, publish
according to PR mode {{pr_mode}}: `draft` opens or updates a draft PR; `ready`
opens or updates a ready-for-review PR. Resolve the authenticated actor through
`{{pack_root}}/assets/scripts/github_api.py actor` and reuse an existing PR only
when the workflow marker, repo/base, authenticated author, and requested mode
are compatible. If a matching marker belongs to another author, record
`foreign_pr_exists` and ask the human how to proceed. V0 never merges.

When `foreign_pr_exists` applies, use the passive wait + mail human gate
pattern before mutating GitHub. This is not a timeout-driven task.

1. Before waiting, update workflow root metadata with:
   - `gc.github.publish_gate=waiting-human`
   - `gc.github.publish_gate_reason=foreign_pr_exists`
   - `gc.github.publish_gate_bead_id=<this bead id>`
   - preserve any existing `gc.github.publish_gate_mail_sent=true`
2. Park the current session so idle handling does not recycle it while the
   human decides:
   ```bash
   SESSION_TARGET="${GC_SESSION_ID:-${GC_SESSION_NAME:-}}"
   SESSION_ATTACH="${GC_SESSION_NAME:-$SESSION_TARGET}"
   WAIT_NOTE="Waiting for human decision on foreign GitHub PR for bead $GC_BEAD_ID."
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
   `gc.github.publish_gate_mail_sent=true`, send exactly one mail with
   `gc mail send human ...`. Include the existing PR URL, existing PR author,
   authenticated actor, requested PR mode, workflow root id, this bead id, and
   requested response options: reuse existing PR, open a new PR, or abort. After
   sending, update workflow root metadata with
   `gc.github.publish_gate_mail_sent=true` and
   `gc.github.publish_gate_mail_to=human`.
4. Wait for explicit human feedback from the active session or mail thread. If
   the session idles, detaches, or restarts before the human responds, do not
   close this bead. A resumed worker must read the gate metadata and continue
   waiting from this gate.

Use `gc.github.publish_gate=approved` only after an explicit human decision and
record the selected publish action. Close fail only for explicit rejection or
abort, not for silence.
