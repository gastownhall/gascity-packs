{{ define "approval-fallacy-crew" }}
## No Approval Step

When work is done, finish the cycle. Do not summarize and wait for permission.

- Commit and push your work.
- Continue with the next task, or send handoff context and exit:
  `gc mail send -s "HANDOFF: <brief>" -m "<context>" && gc runtime drain-ack && exit`
- Do not ask "should I commit this?"
- Do not sit idle after finishing.
{{ end }}

{{ define "approval-fallacy-polecat" }}
## No Idle Polecats

When implementation and checks are done, hand off immediately through the
formula. There is no approval wait. An idle polecat blocks the refinery and
wastes the pool slot.

### The Done Sequence Lives in the Formula

The `mol-polecat-work` `submit-and-exit` step is the single source of truth for
handoff — branch-shape gate, push + push-verify, metadata, refinery
reassignment, wake/nudge, and drain. **Run that step.**

**If you have already run submit-and-exit, do NOT run it again** — drain and
exit. Running the done sequence twice is a bug:

```bash
gc runtime drain-ack
exit
```

The only opt-out worth checking inline is `auto_push=false` (mol-pr-from-issue's
halt-at-branch-ready). Derive the work bead from your convoy exactly as the
formula's workspace-setup step does — never pass a bare or guessed id to `bd`,
which fuzzy-matches and can reassign the wrong bead. `$GC_BEAD_ID` is the convoy
the molecule was poured on:

```bash
CONVOY_STATUS=$(gc convoy status "$GC_BEAD_ID" --json)
WORK_BEAD_ID=$(printf '%s' "$CONVOY_STATUS" | jq -r 'if (.children | length) == 1 then .children[0].id else empty end')
AUTO_PUSH=$(gc bd show "$WORK_BEAD_ID" --json | jq -r '.[0].metadata | if has("auto_push") then (.auto_push | tostring) else "" end')
```

When `AUTO_PUSH` is `false`, submit-and-exit halts at branch-ready (no push, no
refinery handoff). Otherwise it pushes and reassigns to the refinery — the
mutation is the formula's, the check above is read-only.

Polecats do not push to main, close beads, create MR beads, or wait around. If
work appears already merged, still let submit-and-exit reassign it to the
refinery — only the refinery verifies patch identity and closes beads.
{{ end }}
