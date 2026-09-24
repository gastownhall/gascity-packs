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

**Do NOT run submit-and-exit twice** — running the done sequence twice is a bug.
Do not trust memory for this; check mechanically. Derive the work bead from your
convoy exactly as the formula's workspace-setup step does — never pass a bare or
guessed id to `bd`, which fuzzy-matches and can reassign the wrong bead.
`$GC_BEAD_ID` is the convoy the molecule was poured on. If a clean read shows
the work bead is no longer `in_progress` for this session, submit-and-exit
already reassigned it — drain and exit. Otherwise run it:

```bash
EXPECTED_ASSIGNEE="${BEADS_ACTOR:-${GC_SESSION_NAME:-${GC_SESSION_ID:-${GC_AGENT:-}}}}"
# Read the convoy + work bead with retry — same unreadable-is-not-terminal
# discipline as the claim block. An unreadable state (empty JSON, a convoy blip,
# or 0/>=2 children so WORK_BEAD_ID is empty) is NOT proof that submit-and-exit
# already ran. Only a SUCCESSFUL read showing the bead genuinely moved off this
# session (closed, or reassigned to refinery) means it is done.
WORK_BEAD_ID=""
WORK_STATUS=""
WORK_ASSIGNEE=""
READ_OK=0
READ_TRY=0
while [ "$READ_TRY" -lt 3 ]; do
  READ_TRY=$((READ_TRY + 1))
  WORK_BEAD_ID=""
  if [ -n "${GC_BEAD_ID:-}" ]; then
    WORK_BEAD_ID=$(gc convoy status "$GC_BEAD_ID" --json 2>/dev/null \
      | jq -r 'if ((.children // []) | length) == 1 then .children[0].id else empty end' 2>/dev/null)
  fi
  # No convoy is the NORMAL case for a plain-slung bead, so fall back — but only to
  # a bead this session OWNS, never to the dispatcher's trigger record on its own.
  # `gc hook --claim` checks assigned work first and then falls through to the
  # routed pool, so it routinely hands a session a different bead than it was
  # spawned for (measured in gci-utzx's own session: GC_TRIGGER_WORK_BEAD_ID was
  # gci-5ts6 while the claim returned gci-utzx). Reading the wrong bead HERE is
  # not a no-op: it reports ALREADY_SUBMITTED and drains, stranding the real work
  # committed and unpushed. `polecat_session` is stamped at claim time and
  # survives reassignment, so it still names this session after the handoff.
  if [ -z "$WORK_BEAD_ID" ] && [ -n "$EXPECTED_ASSIGNEE" ]; then
    MINE_JSON=$(gc bd list --assignee="$EXPECTED_ASSIGNEE" --status=in_progress --json 2>/dev/null)
    WORK_BEAD_ID=$(printf '%s' "$MINE_JSON" \
      | jq -r 'if (type == "array") and (length == 1) then .[0].id else empty end' 2>/dev/null)
  fi
  if [ -z "$WORK_BEAD_ID" ] && [ -n "$EXPECTED_ASSIGNEE" ]; then
    for CAND in "${GC_TRIGGER_WORK_BEAD_ID:-}" "${GC_TRIGGER_BEAD_ID:-}"; do
      if [ -n "$CAND" ]; then
        CAND_JSON=$(gc bd show "$CAND" --json 2>/dev/null)
        WORK_BEAD_ID=$(printf '%s' "$CAND_JSON" | jq -r --arg me "$EXPECTED_ASSIGNEE" \
          '.[0] | select(((.assignee // "") == $me) or ((.metadata.polecat_session // "") == $me)) | .id' 2>/dev/null)
      fi
      if [ -n "$WORK_BEAD_ID" ]; then break; fi
    done
  fi
  if [ -n "$WORK_BEAD_ID" ]; then
    WORK_JSON=$(gc bd show "$WORK_BEAD_ID" --json 2>/dev/null)
    SHOW_CODE=$?
    WORK_STATUS=$(printf '%s' "$WORK_JSON" | jq -r '.[0].status // empty' 2>/dev/null)
    WORK_ASSIGNEE=$(printf '%s' "$WORK_JSON" | jq -r '.[0].assignee // empty' 2>/dev/null)
    if [ "$SHOW_CODE" -eq 0 ] && [ -n "$WORK_STATUS" ]; then
      READ_OK=1
      break
    fi
  fi
  sleep 1
done
if [ "$READ_OK" -eq 1 ] && { [ "$WORK_STATUS" != "in_progress" ] || [ "$WORK_ASSIGNEE" != "$EXPECTED_ASSIGNEE" ]; }; then
  echo "ALREADY_SUBMITTED $WORK_BEAD_ID status=$WORK_STATUS assignee=$WORK_ASSIGNEE — draining."
  gc runtime drain-ack
  exit
fi
# Unreadable after retries, or still in_progress for this session: DO NOT assume
# already-submitted — fall through and run submit-and-exit. A stranded
# in_progress bead with an unpushed branch is the worse outcome.
```

The push gate is handled inside submit-and-exit itself, and it fails closed:
`auto_push=false` halts at branch-ready (no push, no refinery handoff); an
ABSENT `auto_push` on a bead whose DESCRIPTION or NOTES assert a no-push rail
also halts, and escalates, because absent metadata is not consent; metadata the
gate cannot decode halts and escalates as well (`metadata_unreadable`), because
unreadable metadata is not absent metadata — it is a recorded decision the gate
failed to retrieve — as does an `auto_push` value outside the closed vocabulary
(`false`/`no`/`0` halt, `true`/`yes`/`1` push, case-folded), because a decision
the gate cannot understand is not consent either; consent pushes and reassigns
to the refinery.

Polecats do not push to main, close beads, create MR beads, or wait around. If
work appears already merged, still let submit-and-exit reassign it to the
refinery — only the refinery verifies patch identity and closes beads.
{{ end }}
