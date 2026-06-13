#!/usr/bin/env bash
set -euo pipefail

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

ROOT_JSON="$(bd show "$ROOT_ID" --json 2>/dev/null || true)"
PARENT_ROOT="$(metadata_value "$ROOT_JSON" "gc.root_bead_id")"
if [ -z "$PARENT_ROOT" ]; then
  PARENT_ROOT="$ROOT_ID"
fi

MATCHES="$(bd list --all --metadata-field "gc.root_bead_id=$PARENT_ROOT" --json --limit=0 2>/dev/null || printf '[]')"

VERDICT="$(printf '%s\n' "$MATCHES" | jq -r --arg attempt "$ATTEMPT" '
  [
    .[]
    | select((.metadata["gc.attempt"] // "") == $attempt)
    | select((.metadata["gap_analysis.verdict"] // "") != "")
    | .metadata["gap_analysis.verdict"]
  ] | last // ""
' 2>/dev/null)"

REPORT="$(printf '%s\n' "$MATCHES" | jq -r --arg attempt "$ATTEMPT" '
  [
    .[]
    | select((.metadata["gc.attempt"] // "") == $attempt)
    | select((.metadata["gap_analysis.report_path"] // "") != "")
    | .metadata["gap_analysis.report_path"]
  ] | last // ""
' 2>/dev/null)"

if [ "$VERDICT" != "done" ]; then
  echo "Gap analysis needs another iteration: ${VERDICT:-missing verdict}"
  exit 1
fi

if [ -n "$REPORT" ]; then
  if [ ! -f "$REPORT" ] && [ -n "${GC_WORK_DIR:-}" ] && [ -f "$GC_WORK_DIR/$REPORT" ]; then
    REPORT="$GC_WORK_DIR/$REPORT"
  fi
  if [ -f "$REPORT" ] && grep -Eiq '(^|[^[:alpha:]])severity[^[:alpha:]]*(critical|blocker|major)([^[:alpha:]]|$)' "$REPORT"; then
    echo "Gap analysis report still contains critical/blocker/major findings: $REPORT"
    exit 1
  fi
fi

echo "Gap analysis approved"
exit 0
