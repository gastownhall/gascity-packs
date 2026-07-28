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
Do not trust memory for this; check mechanically. Rediscover your claimed
Graph-v2 submit step with an exact, read-only assignee query, then derive the
source work bead through that step's root and input convoy. Never pass a bare or
guessed id to `bd`, which fuzzy-matches and can mutate the wrong bead.

The source work bead is intentionally open and unassigned before handoff, so
that state is **not** proof of submission. Only a closed source bead or exact
assignment to the configured refinery is terminal evidence. Any other assigned
owner is a conflict and must fail closed.

```bash
# BEGIN_GASTOWN_SUBMIT_GUARD
EXPECTED_ASSIGNEE="${BEADS_ACTOR:-${GC_SESSION_NAME:-${GC_SESSION_ID:-${GC_AGENT:-}}}}"
REFINERY_TARGET="${GC_RIG:+$GC_RIG/}{{ .BindingPrefix }}refinery"
STEP_BEAD_ID=""
ROOT_BEAD_ID=""
WORK_BEAD_ID=""
WORK_STATUS=""
WORK_ASSIGNEE=""
READ_OK=0
READ_TRY=0
if [ -z "$EXPECTED_ASSIGNEE" ]; then
  echo "Cannot identify the current session assignee; refusing done-state inference." >&2
  exit 1
fi
while [ "$READ_TRY" -lt 3 ]; do
  READ_TRY=$((READ_TRY + 1))
  STEP_LIST_JSON=$(gc bd list --assignee "$EXPECTED_ASSIGNEE" --status=in_progress --limit=0 --json 2>/dev/null)
  STEP_LIST_CODE=$?
  STEP_MATCHES=$(printf '%s' "$STEP_LIST_JSON" | jq -c 'if type == "array" then [.[] | select(.metadata["gc.step_ref"] == "mol-polecat-work.submit-and-exit")] else [] end' 2>/dev/null)
  STEP_COUNT=$(printf '%s' "$STEP_MATCHES" | jq -r 'length' 2>/dev/null)
  if [ "$STEP_LIST_CODE" -eq 0 ] && [ "$STEP_COUNT" = "1" ]; then
    STEP_BEAD_ID=$(printf '%s' "$STEP_MATCHES" | jq -r '.[0].id // empty' 2>/dev/null)
    if [ -n "$STEP_BEAD_ID" ]; then
      STEP_JSON=$(gc bd show "$STEP_BEAD_ID" --json 2>/dev/null)
      STEP_CODE=$?
      STEP_STATUS=$(printf '%s' "$STEP_JSON" | jq -r '.[0].status // empty' 2>/dev/null)
      STEP_ASSIGNEE=$(printf '%s' "$STEP_JSON" | jq -r '.[0].assignee // empty' 2>/dev/null)
      STEP_REF=$(printf '%s' "$STEP_JSON" | jq -r '.[0].metadata["gc.step_ref"] // empty' 2>/dev/null)
      ROOT_BEAD_ID=$(printf '%s' "$STEP_JSON" | jq -r '.[0].metadata["gc.root_bead_id"] // empty' 2>/dev/null)
      if [ "$STEP_CODE" -eq 0 ] && [ "$STEP_STATUS" = "in_progress" ] &&
         [ "$STEP_ASSIGNEE" = "$EXPECTED_ASSIGNEE" ] &&
         [ "$STEP_REF" = "mol-polecat-work.submit-and-exit" ] &&
         [ -n "$ROOT_BEAD_ID" ]; then
        ROOT_JSON=$(gc bd show "$ROOT_BEAD_ID" --json 2>/dev/null)
        ROOT_CODE=$?
        INPUT_CONVOY_ID=$(printf '%s' "$ROOT_JSON" | jq -r '.[0].metadata["gc.input_convoy_id"] // empty' 2>/dev/null)
        if [ "$ROOT_CODE" -eq 0 ] && [ -n "$INPUT_CONVOY_ID" ]; then
          CONVOY_STATUS=$(gc convoy status "$INPUT_CONVOY_ID" --json 2>/dev/null)
          CONVOY_CODE=$?
          WORK_BEAD_ID=$(printf '%s' "$CONVOY_STATUS" | jq -r 'if (.children | length) == 1 then .children[0].id else empty end' 2>/dev/null)
          if [ "$CONVOY_CODE" -eq 0 ] && [ -n "$WORK_BEAD_ID" ]; then
            WORK_JSON=$(gc bd show "$WORK_BEAD_ID" --json 2>/dev/null)
            WORK_CODE=$?
            WORK_STATUS=$(printf '%s' "$WORK_JSON" | jq -r '.[0].status // empty' 2>/dev/null)
            WORK_ASSIGNEE=$(printf '%s' "$WORK_JSON" | jq -r '.[0].assignee // empty' 2>/dev/null)
            if [ "$WORK_CODE" -eq 0 ] && [ -n "$WORK_STATUS" ]; then
              READ_OK=1
              break
            fi
          fi
        fi
      fi
    fi
  fi
  sleep 1
done
if [ "$READ_OK" -eq 1 ] &&
   { [ "$WORK_STATUS" = "closed" ] || [ "$WORK_ASSIGNEE" = "$REFINERY_TARGET" ]; }; then
  echo "ALREADY_SUBMITTED $WORK_BEAD_ID status=$WORK_STATUS assignee=$WORK_ASSIGNEE — completing $STEP_BEAD_ID."
  if ! gc bd update "$STEP_BEAD_ID" --set-metadata gc.outcome=pass --status=closed \
       --notes "Submit handoff already complete: source bead $WORK_BEAD_ID status=$WORK_STATUS assignee=$WORK_ASSIGNEE"; then
    echo "Failed to close claimed submit step $STEP_BEAD_ID; refusing to drain." >&2
    exit 1
  fi
  VERIFY_JSON=$(gc bd show "$STEP_BEAD_ID" --json 2>/dev/null)
  VERIFY_STATUS=$(printf '%s' "$VERIFY_JSON" | jq -r '.[0].status // empty' 2>/dev/null)
  VERIFY_OUTCOME=$(printf '%s' "$VERIFY_JSON" | jq -r '.[0].metadata["gc.outcome"] // empty' 2>/dev/null)
  if [ "$VERIFY_STATUS" != "closed" ] || [ "$VERIFY_OUTCOME" != "pass" ]; then
    echo "Submit step $STEP_BEAD_ID did not verify closed/pass; refusing to drain." >&2
    exit 1
  fi
  gc runtime drain-ack
  exit
fi
if [ "$READ_OK" -eq 1 ] &&
   { [ "$WORK_STATUS" != "open" ] || [ -n "$WORK_ASSIGNEE" ]; }; then
  echo "Source bead $WORK_BEAD_ID has conflicting state status=$WORK_STATUS assignee=$WORK_ASSIGNEE; failing $STEP_BEAD_ID." >&2
  if ! gc bd update "$STEP_BEAD_ID" --set-metadata gc.outcome=fail --status=closed \
       --notes "Submit blocked: source bead $WORK_BEAD_ID has conflicting status=$WORK_STATUS assignee=$WORK_ASSIGNEE"; then
    echo "Failed to close conflicting submit step $STEP_BEAD_ID; refusing to drain." >&2
    exit 1
  fi
  VERIFY_JSON=$(gc bd show "$STEP_BEAD_ID" --json 2>/dev/null)
  VERIFY_STATUS=$(printf '%s' "$VERIFY_JSON" | jq -r '.[0].status // empty' 2>/dev/null)
  VERIFY_OUTCOME=$(printf '%s' "$VERIFY_JSON" | jq -r '.[0].metadata["gc.outcome"] // empty' 2>/dev/null)
  if [ "$VERIFY_STATUS" != "closed" ] || [ "$VERIFY_OUTCOME" != "fail" ]; then
    echo "Submit step $STEP_BEAD_ID did not verify closed/fail; refusing to drain." >&2
    exit 1
  fi
  gc runtime drain-ack
  exit 1
fi
# Unreadable after retries or the expected open/unassigned pre-handoff state:
# fall through and run submit-and-exit. This guard never claims routed work.
# END_GASTOWN_SUBMIT_GUARD
```

The `auto_push=false` opt-out (mol-pr-from-issue's halt-at-branch-ready) is
handled inside submit-and-exit itself: when set, it halts at branch-ready (no
push, no refinery handoff); otherwise it pushes and reassigns to the refinery.

Polecats do not push to main, close source work beads, create MR beads, or wait
around. They do close their claimed Graph-v2 step after its prescribed action.
If work appears already merged, still let submit-and-exit reassign the source
bead to the refinery — only the refinery verifies patch identity and closes it.
{{ end }}
