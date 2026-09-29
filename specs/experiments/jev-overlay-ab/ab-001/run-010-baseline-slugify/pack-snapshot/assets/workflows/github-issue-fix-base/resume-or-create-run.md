
Resume the latest active nonterminal issue-fix run by default. If no active run
exists, create one under
artifact-root-relative path
`/github/issues/<owner>/<repo>/<number>/fix/<run-id>/`, resolved with
`{{pack_root}}/assets/scripts/artifacts.py path --override "{{artifact_root}}"
--relative "/github/issues/<owner>/<repo>/<number>/fix/<run-id>/" --mkdir-parents
--directory`. If the issue body hash changed while a run is active, run/reuse
triage for the new hash and ask the human whether to continue the old run with
updated context or start fresh.

When that body-hash decision is required, use the passive wait + mail human
gate pattern before choosing a run directory. This is not a timeout-driven task.

1. Before waiting, update workflow root metadata with:
   - `gc.github.run_selection_gate=waiting-human`
   - `gc.github.run_selection_gate_bead_id=<this bead id>`
   - preserve any existing `gc.github.run_selection_gate_mail_sent=true`
2. Park the current session so idle handling does not recycle it while the
   human decides:
   ```bash
   SESSION_TARGET="${GC_SESSION_ID:-${GC_SESSION_NAME:-}}"
   SESSION_ATTACH="${GC_SESSION_NAME:-$SESSION_TARGET}"
   WAIT_NOTE="Waiting for human decision on GitHub issue fix run selection for bead $GC_BEAD_ID."
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
   `gc.github.run_selection_gate_mail_sent=true`, send exactly one mail with
   `gc mail send human ...`. Include the old run directory, old body hash, new
   body hash, new triage artifact path, workflow root id, this bead id, GitHub
   issue URL, and requested response options: continue old run with updated
   context, or start fresh. After sending, update workflow root metadata with
   `gc.github.run_selection_gate_mail_sent=true` and
   `gc.github.run_selection_gate_mail_to=human`.
4. Wait for explicit human feedback from the active session or mail thread. If
   the session idles, detaches, or restarts before the human responds, do not
   close this bead. A resumed worker must read the gate metadata and continue
   waiting from this gate.

Use `gc.github.run_selection_gate=continue_old` or `start_fresh` only after an
explicit human decision. Close fail only for explicit rejection or abort, not
for silence.

This step owns the issue-fix artifact path contract. Once the active run
directory is known, resolve these absolute paths under that run directory:

- `requirements.md`
- `implementation-plan.md`

Then publish all path metadata on the workflow root in one update:

```bash
gc bd update <root-bead-id> \
  --set-metadata gc.github.run_dir=<absolute run directory> \
  --set-metadata gc.github.requirements_path=<absolute requirements.md path> \
  --set-metadata gc.github.implementation_plan_path=<absolute implementation-plan.md path> \
  --set-metadata gc.github.design_path=<same absolute implementation-plan.md path>
```

`gc.github.design_path` is only a legacy alias for consumers that still use the
old key. It must point at the same file as `gc.github.implementation_plan_path`.
Do not schedule a separate design compatibility step and do not create
`design.md`.
