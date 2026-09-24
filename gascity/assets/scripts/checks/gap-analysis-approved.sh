#!/usr/bin/env bash
set -euo pipefail

gmol() {   # root_id -> molecule-member JSON array
    # `gc bd list --metadata-field` is a collection query carrying no bead id,
    # so on a city that relocates the graph class bd has nothing to route on and
    # refuses the read -- and the `2>/dev/null` below turned that refusal into an
    # empty set, so this gate never saw gap_analysis.verdict and looped until Ralph
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
    # newest `updated_at` by value, and only when every candidate is dated,
    # then reduces what is left fail-closed; the report check (REPORTS) walks
    # every distinct report path at the attempt instead of the id-last one.
    jq -s 'map(select(type=="array")) | add // [] | unique_by(.id)' "$tmp"/*.json || rc=1
    rm -rf "$tmp"
    return "$rc"
}

ROOT_ID="${GC_BEAD_ID:-}"
ATTEMPT="${GC_ITERATION:-}"

if [ -z "$ROOT_ID" ]; then
  echo "gap check: GC_BEAD_ID is required" >&2
  exit 1
fi

if [ -z "$ATTEMPT" ]; then
  ATTEMPT="0"
fi

metadata_value() {
  local json="$1"
  local key="$2"
  printf '%s\n' "$json" | jq -r --arg key "$key" '
    (if type == "array" then (.[0] // {}) else . end)
    | .metadata[$key] // empty
  ' 2>/dev/null
}

# The one approval vocabulary, shared with design-review-approved.sh and
# implementation-review-approved.sh. Both consumers here -- the jq verdict
# selection and the bash dispatch -- read this single definition and match
# case-insensitively. This gate used to accept `done` alone. It now reads the
# shared vocabulary; no writer of `gap_analysis.verdict` exists in the
# repository, so no live loop changes behavior.
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

GC_ERR="$(mktemp)"
# EXIT alone does not fire on an untrapped signal, and check gates run under a
# documented 10m dispatcher budget -- timeout kills are an expected path, not a
# hypothetical one, so each would leak this capture file. SIGKILL leaks either way.
trap 'rm -f "$GC_ERR"' EXIT INT TERM HUP
if ! ROOT_JSON="$(gc bd show "$ROOT_ID" --json 2>"$GC_ERR")"; then
  echo "gap check: note: gc bd show $ROOT_ID failed: $(tail -c 400 "$GC_ERR" | tr '\n' ' ')" >&2
fi
PARENT_ROOT="$(metadata_value "$ROOT_JSON" "gc.root_bead_id")"
if [ -z "$PARENT_ROOT" ]; then
  PARENT_ROOT="$ROOT_ID"
fi

MATCHES="$(gmol "$PARENT_ROOT")"

# No writer of `gap_analysis.verdict` exists and there is no lane grammar to
# detect, so there is no owner partition here; the gate reduces by value
# alone. jq emits two lines: the selected verdict, then an optional note.
VERDICT_SELECTION="$(printf '%s\n' "$MATCHES" | jq -r \
  --arg attempt "$ATTEMPT" \
  --argjson approvals "$APPROVAL_VERDICTS_JSON" '
  def is_approval($value):
    (($value // "") | ascii_downcase) as $v
    | any($approvals[]; . == $v);
  def newest($rows):
    ($rows | map(select((.updated_at // "") != "")) | length) as $dated
    | if $dated > 0 and $dated == ($rows | length)
      then ($rows | map(.updated_at) | max) as $max
        | ($rows | map(select(.updated_at == $max)))
      else $rows
      end;
  def decide($rows):
    ($rows | map(.value) | unique) as $vals
    | ($vals | map(select(is_approval(.) | not))) as $blocking
    | if ($blocking | length) > 0 then $blocking[0] else ($vals[0] // "") end;
  [
    .[]
    | select((.metadata["gc.attempt"] // "") == $attempt)
    | select((.metadata["gap_analysis.verdict"] // "") != "")
    | {value: .metadata["gap_analysis.verdict"], updated_at: (.updated_at // "")}
  ] as $candidates
  | ($candidates | map(.value) | unique) as $values
  | newest($candidates) as $current
  | decide($current) as $verdict
  | (
      if (($current | map(.value) | unique | length) > 1) then
        "fail-closed among \($current | map(.value) | unique | length) values"
      elif (($current | length) < ($candidates | length)) then
        "newest updated_at"
      else
        "unanimous"
      end
    ) as $basis
  | (
      if ($candidates | length) > 1 then
        "gap check: \($candidates | length) beads carry gap_analysis.verdict at attempt \($attempt) (values: \($values | join(", "))); selected \"\($verdict)\" (\($basis))"
      else
        ""
      end
    ) as $note
  | "\($verdict)\n\($note)"
' 2>/dev/null)"
VERDICT="$(printf '%s\n' "$VERDICT_SELECTION" | sed -n '1p')"
VERDICT_NOTE="$(printf '%s\n' "$VERDICT_SELECTION" | sed -n '2p')"
if [ -n "$VERDICT_NOTE" ]; then
  echo "$VERDICT_NOTE" >&2
fi

REPORTS="$(printf '%s\n' "$MATCHES" | jq -r --arg attempt "$ATTEMPT" '
  [
    .[]
    | select((.metadata["gc.attempt"] // "") == $attempt)
    | (.metadata["gap_analysis.report_path"] // "")
    | select(. != "")
  ] | unique | .[]
' 2>/dev/null)"

if ! is_approved "$VERDICT"; then
  case "$VERDICT" in
    iterate|fail|retry|"") : ;;
    *) echo "gap check: unknown gap-analysis verdict: $VERDICT" >&2 ;;
  esac
  echo "Gap analysis needs another iteration: ${VERDICT:-missing verdict}"
  exit 1
fi

# Every distinct report recorded at this attempt is checked, not the id-last
# one: the severity grep can only fail the gate, so a stale report at the same
# attempt costs one more iteration rather than hiding a critical finding.
# `unique` sorts the paths, so the first hit is the same whichever bead is
# id-last.
while IFS= read -r REPORT; do
  [ -n "$REPORT" ] || continue
  if [ ! -f "$REPORT" ] && [ -n "${GC_WORK_DIR:-}" ] && [ -f "$GC_WORK_DIR/$REPORT" ]; then
    REPORT="$GC_WORK_DIR/$REPORT"
  fi
  if [ -f "$REPORT" ] && grep -Eiq '(^|[^[:alpha:]])severity[^[:alpha:]]*(critical|blocker|major)([^[:alpha:]]|$)' "$REPORT"; then
    echo "Gap analysis report still contains critical/blocker/major findings: $REPORT"
    exit 1
  fi
done <<<"$REPORTS"

echo "Gap analysis approved"
exit 0
