Confirm Superpowers design approval.

This lane represents the stock `User approves design?` gate before writing the
spec. Use workflow root metadata `gc.var.brainstorming_approval_mode` when
present; otherwise default to `autonomous`.

In `interactive` mode, use the passive wait + mail human gate pattern. This is
not a timeout-driven task.

1. Before waiting, update workflow root metadata with:
   - `gc.build.design_gate_status=waiting-human`
   - `gc.build.design_gate_bead_id=<this bead id>`
   - `gc.build.design_gate_artifact_path=<approval-summary path>`
   - preserve any existing `gc.build.design_gate_mail_sent=true`
2. Park the current session so idle handling does not recycle it while the
   human decides:
   ```bash
   SESSION_TARGET="${GC_SESSION_ID:-${GC_SESSION_NAME:-}}"
   SESSION_ATTACH="${GC_SESSION_NAME:-$SESSION_TARGET}"
   WAIT_NOTE="Waiting for human approval of Superpowers design on bead $GC_BEAD_ID."
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
   `gc.build.design_gate_mail_sent=true`, send exactly one mail with
   `gc mail send human ...`. Include the design candidate path, approval
   summary path, workflow root id, this bead id, and the requested response
   options: approve, request changes, or reject. After sending, update workflow
   root metadata with `gc.build.design_gate_mail_sent=true` and
   `gc.build.design_gate_mail_to=human`.
4. Wait for explicit human feedback from the active session or mail thread. If
   the session idles, detaches, or
   restarts before the human responds, do not close this bead. A resumed worker
   must read the gate metadata and continue waiting from this gate.
5. Use `done` only after explicit approval by setting
   `design_review.verdict=done`. If the human requests changes, record the
   requested revisions in the approval summary and close with
   `design_review.verdict=iterate`; that re-opens the design loop for another
   brainstorming pass. Close fail only for explicit rejection or abort, not for
   silence.

In `autonomous` mode, approve only when the design candidate has no unresolved
questions, no placeholders, and enough context to proceed without inventing
requirements. Otherwise close with `design_review.verdict=iterate`; that
re-opens the design loop for another brainstorming pass.

When iterating, write a concise revision summary that the next
`brainstorm-design` attempt can apply directly. The summary must name the
specific design sections, assumptions, or unresolved questions that caused the
loopback.

On approval, mark the design candidate approved and update workflow root
metadata with `gc.build.design_status=approved`,
`gc.build.design_path=<absolute path>`, `gc.build.design_gate_status=approved`,
and a short design summary. For a human-requested iteration, update
`gc.build.design_gate_status=revision_requested`.

Before closing, update the exact claimed bead id with the lane metadata. The
approval verdict metadata is `design_review.verdict=done|iterate`:

```bash
bd update "$CLAIMED_BEAD_ID" \
  --set-metadata 'gc.outcome=pass' \
  --set-metadata 'design_review.verdict=done' \
  --set-metadata 'design_review.output_path=<approval-summary path>' \
  --set-metadata 'gc.continuation_group=superpowers-design-fixes'
bd close "$CLAIMED_BEAD_ID" --reason 'Superpowers design approved.'
```

If the design needs another pass, set `design_review.verdict=iterate` instead
of `done` and name the required correction in the approval summary and close
reason. Do not pass `--metadata` or `--set-metadata` to `bd close`.

Do not invoke provider-native subagents or upstream plugin runtime commands.
This Gas City lane owns the design approval decision.
