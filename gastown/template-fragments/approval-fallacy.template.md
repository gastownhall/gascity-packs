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
if ! SUBMIT_GUARD_OUTPUT=$(gc gastown polecat-submit guard); then
  echo "Deterministic submit-state guard failed closed; do not run submit-and-exit." >&2
  exit 1
fi
if ! printf '%s' "$SUBMIT_GUARD_OUTPUT" | jq -e '
  type == "object" and
  (keys | sort) ==
    (["action", "assignee", "branch", "contract", "convoy", "mode",
      "replay", "root", "source", "source_assignee", "status", "step"] |
     sort) and
  .contract == "polecat-submit.v1" and
  (.action | IN("proceed", "terminal")) and
  (.step | type) == "string" and (.step | length) > 0 and
  (.assignee | type) == "string" and (.assignee | length) > 0 and
  (.root | type) == "string" and (.root | length) > 0 and
  (.convoy | type) == "string" and (.convoy | length) > 0 and
  (.source | type) == "string" and (.source | length) > 0 and
  (.branch | type) == "string" and .branch == ("polecat/" + .source) and
  (.mode | type) == "string" and
  (.status | type) == "string" and
  (.source_assignee | type) == "string" and
  (.replay | type) == "boolean" and
  (if .action == "proceed"
   then .mode == "" and .status == "open" and
        .source_assignee == "" and .replay == false
   else (.mode | IN("auto_push_false", "refinery")) and
        (if .mode == "auto_push_false"
         then .status == "open" and .source_assignee == ""
         else (.status | IN("open", "in_progress", "closed"))
         end)
   end)
' >/dev/null 2>&1; then
  echo "Unsupported deterministic submit-state result; refusing done-state inference." >&2
  exit 1
fi
SUBMIT_GUARD_ACTION=$(printf '%s' "$SUBMIT_GUARD_OUTPUT" | jq -er '.action')
case "$SUBMIT_GUARD_ACTION" in
  proceed)
    echo "$SUBMIT_GUARD_OUTPUT"
    ;;
  terminal)
    echo "$SUBMIT_GUARD_OUTPUT"
    SUBMIT_CONVOY=$(printf '%s' "$SUBMIT_GUARD_OUTPUT" | jq -er '.convoy')
    SUBMIT_SOURCE=$(printf '%s' "$SUBMIT_GUARD_OUTPUT" | jq -er '.source')
    SUBMIT_BRANCH=$(printf '%s' "$SUBMIT_GUARD_OUTPUT" | jq -er '.branch')
    SUBMIT_EVIDENCE_MODE=$(printf '%s' "$SUBMIT_GUARD_OUTPUT" | jq -er '.mode')
    if ! gc gastown polecat-submit complete \
         --convoy "$SUBMIT_CONVOY" \
         --source "$SUBMIT_SOURCE" \
         --branch "$SUBMIT_BRANCH" \
         --mode "$SUBMIT_EVIDENCE_MODE"; then
      echo "Deterministic terminal submit completion failed; refusing to drain." >&2
      exit 1
    fi
    if ! gc runtime drain-ack; then
      echo "Submit completion is durable but drain acknowledgement failed; retry the guard." >&2
      exit 1
    fi
    exit 0
    ;;
  *)
    echo "Unsupported deterministic submit-state result; refusing done-state inference." >&2
    exit 1
    ;;
esac
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
