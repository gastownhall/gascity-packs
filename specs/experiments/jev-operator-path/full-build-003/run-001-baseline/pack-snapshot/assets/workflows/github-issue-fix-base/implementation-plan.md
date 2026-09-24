
Selected planning methodology formula: {{planning_formula}}.

Use the mayor implementation-plan procedure over the approved generated
requirements. In `interactive` mode, human-gate the implementation plan
artifact. In `autonomous` mode, generate and approve the implementation plan
non-interactively while recording the autonomous decision in the run artifacts.
In `headless` mode, behave like `autonomous` but never ask questions; if
required input is missing, stop blocked with a machine-readable
`gc.blocked_reason`. The launch alias is mode {{mode}}; read the effective
interaction mode from `gc.var.interaction_mode` on the workflow root.

Concrete issue-fix wrappers may override this step to delegate to
`{{planning_formula}}`, but they must still write the same
`gc.github.implementation_plan_path` artifact and preserve the human-gate
metadata protocol.

Read `gc.github.implementation_plan_path` from workflow root metadata and write
the approved artifact to that absolute path. Do not choose or invent a
different path. If the metadata is missing or points outside the run directory,
fail hard instead of guessing a run directory.

Downstream design-review and create-beads steps must read the artifact through
`gc.github.implementation_plan_path`. The legacy `gc.github.design_path` alias
is already set by `resume-or-create-run` and must point at this same file.

In `interactive` mode, use the passive wait + mail human gate pattern after
writing the implementation plan artifact. This is not a timeout-driven task.

1. Before waiting, update workflow root metadata with:
   - `gc.github.implementation_plan_gate=waiting-human`
   - `gc.github.implementation_plan_gate_bead_id=<this bead id>`
   - preserve any existing `gc.github.implementation_plan_gate_mail_sent=true`
2. Park the current session so idle handling does not recycle it while the
   human decides:
   ```bash
   SESSION_TARGET="${GC_SESSION_ID:-${GC_SESSION_NAME:-}}"
   SESSION_ATTACH="${GC_SESSION_NAME:-$SESSION_TARGET}"
   WAIT_NOTE="Waiting for human approval of GitHub issue fix plan on bead $GC_BEAD_ID."
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
   `gc.github.implementation_plan_gate_mail_sent=true`, send exactly one mail
   with `gc mail send human ...`. Include the implementation plan path,
   workflow root id, this bead id, GitHub issue URL, and requested response
   options: approve, request changes, or reject. After sending, update workflow
   root metadata with `gc.github.implementation_plan_gate_mail_sent=true` and
   `gc.github.implementation_plan_gate_mail_to=human`.
4. Wait for explicit human feedback from the active session or mail thread. If
   the session idles, detaches, or restarts before the human responds, do not
   close this bead. A resumed worker must read the gate metadata and continue
   waiting from this gate.

Use `gc.github.implementation_plan_gate=approved` only after explicit human
approval. Use `revision_requested` when the plan must be revised before
downstream design review. Close fail only for explicit rejection or abort, not
for silence.
