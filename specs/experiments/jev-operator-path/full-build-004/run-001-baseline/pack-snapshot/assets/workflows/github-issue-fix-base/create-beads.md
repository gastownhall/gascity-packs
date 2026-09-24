
Selected decomposition methodology formula: {{decomposition_formula}}.

Use the mayor create beads procedure over approved requirements and the
implementation plan. In `interactive` mode, human-gate bead creation/start. In
`autonomous` mode, generate and approve `tasks.md`, then create the task beads
and implementation convoy non-interactively. In `headless` mode, behave like
`autonomous` but never ask questions; if required input is missing, stop
blocked with a machine-readable `gc.blocked_reason`. Each issue-fix run owns
one generated implementation convoy; review-fix passes remain
iteration-specific. The `tasks.md` front matter must use
`implementation_plan_file`. The launch alias is mode {{mode}}; read the
effective interaction mode from `gc.var.interaction_mode` on the workflow
root.

Concrete issue-fix wrappers may override this step to delegate to
`{{decomposition_formula}}`, but the output must still be the implementation
convoy consumed by the selected implementation formula.

In `interactive` mode, use the passive wait + mail human gate pattern after
writing `tasks.md` and before creating beads or starting the implementation
convoy. This is not a timeout-driven task.

1. Before waiting, update workflow root metadata with:
   - `gc.github.create_beads_gate=waiting-human`
   - `gc.github.create_beads_gate_bead_id=<this bead id>`
   - preserve any existing `gc.github.create_beads_gate_mail_sent=true`
2. Park the current session so idle handling does not recycle it while the
   human decides:
   ```bash
   SESSION_TARGET="${GC_SESSION_ID:-${GC_SESSION_NAME:-}}"
   SESSION_ATTACH="${GC_SESSION_NAME:-$SESSION_TARGET}"
   WAIT_NOTE="Waiting for human approval to create GitHub issue fix beads on bead $GC_BEAD_ID."
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
   `gc.github.create_beads_gate_mail_sent=true`, send exactly one mail with
   `gc mail send human ...`. Include the `tasks.md` path, implementation plan
   path, workflow root id, this bead id, GitHub issue URL, and requested
   response options: approve, request changes, or reject. After sending, update
   workflow root metadata with `gc.github.create_beads_gate_mail_sent=true` and
   `gc.github.create_beads_gate_mail_to=human`.
4. Wait for explicit human feedback from the active session or mail thread. If
   the session idles, detaches, or restarts before the human responds, do not
   close this bead. A resumed worker must read the gate metadata and continue
   waiting from this gate.

Use `gc.github.create_beads_gate=approved` only after explicit human approval,
then create the task beads and implementation convoy. Use `revision_requested`
when `tasks.md` must be revised before bead creation. Close fail only for
explicit rejection or abort, not for silence.
