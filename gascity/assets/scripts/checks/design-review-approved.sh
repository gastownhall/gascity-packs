#!/usr/bin/env bash
# Check script for github-issue-fix design-review retry loops.

set -euo pipefail

gmol() {   # root_id -> molecule-member JSON array
    # `gc bd list --metadata-field` is a collection query carrying no bead id,
    # so on a city that relocates the graph class bd has nothing to route on and
    # refuses the read -- and the `2>/dev/null` below turned that refusal into an
    # empty set, so this gate never saw design_review.verdict and looped until Ralph
    # ran out of attempts.
    #
    # `gc ready` is the federating reader: city store, rig stores and the
    # relocated graph store, across both tiers. It takes exactly one --status
    # and has no --all, so the member set is the union of one leg per status.
    # The four legs are independent reads, so run them concurrently: a check
    # gate has a 10m budget and each `gc ready` costs ~17s on a loaded city.
    # A leg that fails is reported on stderr and fails the function rather than
    # contributing an empty set -- silent starvation is the bug being fixed.
    local root="$1" tmp st rc=0
    tmp="$(mktemp -d)" || return 1
    for st in open in_progress blocked closed; do
        { gc ready --metadata-field "gc.root_bead_id=$root" --status "$st" --limit 0 --json \
            >"$tmp/$st.json" || printf '%s\n' "$st" >>"$tmp/failed"; } &
    done
    wait
    if [ -s "$tmp/failed" ]; then
        echo "gmol: gc ready failed for status: $(tr '\n' ' ' <"$tmp/failed")" >&2
        rc=1
    fi
    # unique_by sorts by id, so the union comes back in bead-id order, and
    # that is the only order it has. `updated_at` is `omitempty,omitzero` on
    # the reader's bead struct, so `gc ready --json` emits it on every row in
    # some deployments and on none in others -- both measured: 56/56 rows on
    # the PR #376 review root, 0/37 on a gc 1.4.1 rig store. The re-sort this
    # line used to carry was live in one world and inert in the other, and in
    # both it only staged row order for a positional `| last` downstream.
    #
    # It is gone because nothing in this file decides by row position any
    # more. The verdict selection below (VERDICT_SELECTION) narrows to the
    # highest attempt, then to owner-shaped beads, then to the newest
    # `updated_at` -- each by value, and recency only when every candidate is
    # dated -- and reduces whatever is left fail-closed. That selection is
    # invariant under a permutation of bead ids, which is the property the old
    # `| last` could not hold.
    jq -s 'map(select(type=="array")) | add // [] | unique_by(.id)' "$tmp"/*.json || rc=1
    rm -rf "$tmp"
    return "$rc"
}

BEAD_ID="${GC_BEAD_ID:-}"
if [ -z "$BEAD_ID" ]; then
    echo "ERROR: GC_BEAD_ID not set" >&2
    exit 1
fi

GC_ERR="$(mktemp)"
# EXIT alone does not fire on an untrapped signal, and check gates run under a
# documented 10m dispatcher budget -- timeout kills are an expected path, not a
# hypothetical one, so each would leak this capture file. SIGKILL leaks either way.
trap 'rm -f "$GC_ERR"' EXIT INT TERM HUP
BEAD_JSON=$(gc bd show "$BEAD_ID" --json 2>"$GC_ERR") || {
    echo "ERROR: gc bd show $BEAD_ID failed: $(tail -c 400 "$GC_ERR" | tr '\n' ' ')" >&2
    exit 1
}
ROOT_ID=$(printf '%s\n' "$BEAD_JSON" | jq -r 'if type == "array" then (.[0].metadata["gc.root_bead_id"] // "") else (.metadata["gc.root_bead_id"] // "") end')
ATTEMPT=$(printf '%s\n' "$BEAD_JSON" | jq -r 'if type == "array" then (.[0].metadata["gc.attempt"] // "") else (.metadata["gc.attempt"] // "") end')
SCOPE_REF=$(printf '%s\n' "$BEAD_JSON" | jq -r 'if type == "array" then (.[0].metadata["gc.scope_ref"] // .[0].metadata["gc.step_ref"] // "") else (.metadata["gc.scope_ref"] // .metadata["gc.step_ref"] // "") end')
STEP_ID=$(printf '%s\n' "$BEAD_JSON" | jq -r 'if type == "array" then (.[0].metadata["gc.step_id"] // "") else (.metadata["gc.step_id"] // "") end')
if [ -z "$ROOT_ID" ]; then
    echo "ERROR: missing gc.root_bead_id on $BEAD_ID" >&2
    exit 1
fi

# The one approval vocabulary. Both consumers read this single definition and
# both match case-insensitively: the jq verdict selection, which receives it
# via --argjson, and the bash dispatch at the bottom of the file. A spelling
# added here reaches every consumer at once -- in any case, because each
# consumer downcases the entry as well as the candidate. Matching only the
# candidate would have made a mixed-case entry silently unmatchable everywhere,
# which is the same class of defect as the split vocabulary this replaced.
APPROVAL_VERDICTS=(approve approved pass done)
APPROVAL_VERDICTS_JSON="$(printf '%s\n' "${APPROVAL_VERDICTS[@]}" \
  | jq -Rsc 'split("\n") | map(select(. != "")) | map(ascii_downcase)')"

is_approved() {
  local candidate known
  candidate="$(printf '%s' "${1-}" | tr '[:upper:]' '[:lower:]')"
  [ -n "$candidate" ] || return 1
  for known in "${APPROVAL_VERDICTS[@]}"; do
    if [ "$candidate" = "${known,,}" ]; then
      return 0
    fi
  done
  return 1
}

# One bead owns the loop verdict: the six apply/confirm lanes contracted to
# write the bare `design_review.verdict`. Every review lane instead writes a
# suffixed key (`design_review.review_verdict`, `plan_review.founder_verdict`,
# and siblings) and is contracted not to write the bare one, so a candidate
# carrying any `^(design_review|plan_review)\..+_verdict$` key is a lane and is
# dropped -- unless dropping the lanes would leave nothing, in which case every
# candidate is kept. Narrowing may never starve the gate.
#
# Candidates are narrowed to the highest `attempt` first, because that is what
# the old `sort_by(.attempt, .updated_at) | last` keyed on: putting the owner
# partition first would let a stale owner from an earlier iteration outrank the
# current iteration's only candidate, which today's gate never does.
#
# The survivors are then reduced to one value in two steps, neither of them
# positional. First recency: keep only the survivors carrying the newest
# `updated_at`, but only when every survivor is dated -- `updated_at` is
# omitempty, and ranking a partially dated set would silently rank the undated
# rows oldest, which is a guess, not a reading. Then, among values recency
# could not separate, prefer a NON-approving one: resolving an unresolvable
# dispute toward "approve" ships an unreviewed change, while resolving it
# toward "iterate" costs one more loop iteration in a state that should not
# occur anyway. Both steps are invariant under a permutation of bead ids.
#
# jq emits two lines: the selected verdict, then an optional ambiguity note --
# emitted for every multi-candidate reduction, including a unanimous one.
VERDICT_SELECTION=$(
    gmol "$ROOT_ID" |
        jq -r --arg root "$ROOT_ID" --arg attempt "$ATTEMPT" --arg scope "$SCOPE_REF" --arg step "$STEP_ID" \
              --argjson approvals "$APPROVAL_VERDICTS_JSON" '
            def is_approval($value):
              (($value // "") | ascii_downcase) as $v
              | any($approvals[]; . == $v);
            # Narrow to the newest rows -- but only when every row is dated.
            # `updated_at` is omitempty, and ranking a partially dated set would
            # silently rank the undated rows oldest, which is a guess, not a
            # reading. Selecting by max value rather than by position keeps ties
            # whole for the reduction below.
            def newest($rows):
              ($rows | map(select((.updated_at // "") != "")) | length) as $dated
              | if $dated > 0 and $dated == ($rows | length)
                then ($rows | map(.updated_at) | max) as $max
                  | ($rows | map(select(.updated_at == $max)))
                else $rows
                end;
            # Reduce to one value, fail-closed: the lexicographically smallest
            # distinct non-approving value if there is one, else the smallest
            # approval.
            def decide($rows):
              ($rows | map(.value) | unique) as $vals
              | ($vals | map(select(is_approval(.) | not))) as $blocking
              | if ($blocking | length) > 0 then $blocking[0] else ($vals[0] // "") end;
            [
              .[]
              | select(.metadata["gc.root_bead_id"] == $root)
              | select(($attempt == "") or ((.metadata["gc.attempt"] // "") == $attempt))
              | select(
                  if $attempt != "" and $scope != "" then
                    ((.metadata["gc.scope_ref"] // "") == $scope)
                  elif $step != "" then
                    ((.metadata["gc.ralph_step_id"] // "") == $step) or
                    (((.metadata["gc.scope_ref"] // "") | startswith($step + ".iteration.")))
                  elif $scope != "" then
                    ((.metadata["gc.scope_ref"] // "") == $scope)
                  else
                    ((.metadata["gc.continuation_group"] // "") == "design-review-fixes")
                  end
                )
              | select((.metadata["design_review.verdict"] // "") != "")
              | {
                  value: .metadata["design_review.verdict"],
                  attempt: ((.metadata["gc.attempt"] // "0") | tonumber? // 0),
                  updated_at: (.updated_at // ""),
                  lane: (
                    [(.metadata // {}) | keys[] | select(test("^(design_review|plan_review)\\..+_verdict$"))]
                    | length > 0
                  )
                }
            ] as $scoped
            | (if ($scoped | length) > 0 then ($scoped | map(.attempt) | max) else 0 end) as $top
            | ($scoped | map(select(.attempt == $top))) as $candidates
            | ($candidates | map(select(.lane | not))) as $owners
            | (if ($owners | length) > 0 then $owners else $candidates end) as $surviving
            | ($surviving | map(.value) | unique) as $values
            | newest($surviving) as $current
            | decide($current) as $verdict
            | (
                if (($current | map(.value) | unique | length) > 1) then
                  "fail-closed among \($current | map(.value) | unique | length) values"
                elif (($current | length) < ($surviving | length)) then
                  "newest updated_at"
                else
                  "unanimous"
                end
              ) as $basis
            | (
                if ($owners | length) > 1 then
                  "design review check: \($owners | length) owner-shaped beads carry design_review.verdict at attempt \($top) (values: \($values | join(", "))); selected \"\($verdict)\" (\($basis))"
                elif ($owners | length) == 0 and ($surviving | length) > 1 then
                  "design review check: no owner-shaped bead at attempt \($top); reduced \($surviving | length) lane candidates (values: \($values | join(", "))); selected \"\($verdict)\" (\($basis))"
                else
                  ""
                end
              ) as $note
            | "\($verdict)\n\($note)"
        '
)
VERDICT=$(printf '%s\n' "$VERDICT_SELECTION" | sed -n '1p')
VERDICT_NOTE=$(printf '%s\n' "$VERDICT_SELECTION" | sed -n '2p')
if [ -n "$VERDICT_NOTE" ]; then
    echo "$VERDICT_NOTE" >&2
fi

if is_approved "$VERDICT"; then
    echo "Design review approved"
    exit 0
fi
case "$VERDICT" in
    iterate|fail|retry|"")
        echo "Design review needs another pass"
        exit 1
        ;;
    *)
        echo "Unknown design-review verdict: $VERDICT" >&2
        exit 1
        ;;
esac
