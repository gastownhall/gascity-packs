#!/usr/bin/env bash
#
# nudge-project-leads.sh — wake every project-lead session for a triage tick.
#
# Pure plumbing: enumerate active project-lead sessions, send each one
# the standard triage nudge. The decision of "what to escalate" stays
# entirely with the project-lead (informed by its rig's project-brief.md).
# This script never reads beads, never decides escalations.

set -euo pipefail

# Session template for this pack's project-lead. Rig-scoped sessions carry a
# rig-qualified template (`<rig>/oversight-rig.project-lead`), so match both.
template="oversight-rig.project-lead"

# `gc session list --json` returns an object; the sessions are under `.sessions`.
mapfile -t session_ids < <(
  gc session list --json \
    | jq -r --arg t "$template" '
        .sessions[]
        | select(.state == "active")
        | select((.template // "") as $tpl | $tpl == $t or ($tpl | endswith("/" + $t)))
        | .id'
)

if [[ ${#session_ids[@]} -eq 0 ]]; then
  echo "no active project-lead sessions"
  exit 0
fi

nudged=0
for sid in "${session_ids[@]}"; do
  if gc session nudge "$sid" --message "Triage tick: read your brief, survey your rig, write rollups." >/dev/null 2>&1; then
    nudged=$((nudged + 1))
  else
    echo "nudge failed for $sid" >&2
  fi
done

echo "nudged $nudged project-lead session(s)"
