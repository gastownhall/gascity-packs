#!/usr/bin/env bash
#
# nudge-project-leads.sh — wake every project-lead session for a triage tick.
#
# Pure plumbing: enumerate active project-lead sessions, send each one
# the standard triage nudge. The decision of "what to escalate" stays
# entirely with the project-lead (informed by its rig's project-brief.md).
# This script never reads beads, never decides escalations.
#
# A project-lead is any active session whose template's last path segment is
# "project-lead" or ends in ".project-lead". The template cannot be hardcoded:
# the agent is rig-scoped, so it carries a "<rig>/" prefix, and its binding is
# whatever name the city imported this pack under ("<rig>/<binding>.project-lead").
#
# Exit status: 0 when every selected session was nudged (or none is active);
# 1 when the session listing cannot be read or any nudge failed. A listing
# failure must not read as "no active sessions".

set -euo pipefail

message="Triage tick: read your brief, survey your rig, write rollups."

# Read the listing into a variable first. Parsing it inside a process
# substitution would turn a failing gc or jq into an empty list and exit 0.
if ! listing="$(gc session list --json)"; then
  echo "nudge-project-leads: gc session list --json failed" >&2
  exit 1
fi
# jq reads empty input as no values and exits 0, so empty output would pass
# for an empty listing.
if [[ -z "${listing//[[:space:]]/}" ]]; then
  echo "nudge-project-leads: gc session list --json printed nothing" >&2
  exit 1
fi

# gc emits an envelope with a "sessions" array: {schema_version, filters,
# sessions, summary} locally, {_cache_age_s, sessions} through the API.
# Releases before v1.2.0 emitted a bare array. Accept those, refuse the rest.
if ! ids="$(jq -r '
    (if type == "array" then . elif type == "object" then .sessions else null end)
    | if type == "array" then . else error("no session list in gc session list --json output") end
    | .[]
    | select(.state == "active" and (.closed // false | not))
    | select((.template // "") | split("/") | (last // "") | test("(^|\\.)project-lead$"))
    | .id
  ' <<<"$listing")"; then
  echo "nudge-project-leads: could not parse gc session list --json output" >&2
  exit 1
fi

session_ids=()
while IFS= read -r sid; do
  if [[ -n "$sid" ]]; then
    session_ids+=("$sid")
  fi
done <<<"$ids"

if [[ ${#session_ids[@]} -eq 0 ]]; then
  echo "no active project-lead sessions"
  exit 0
fi

nudged=0
failed=0
for sid in "${session_ids[@]}"; do
  # The message is positional: `gc session nudge <id-or-alias> <message...>`.
  if out="$(gc session nudge "$sid" "$message" 2>&1)"; then
    nudged=$((nudged + 1))
  else
    failed=$((failed + 1))
    echo "nudge failed for $sid: $out" >&2
  fi
done

echo "nudged $nudged of ${#session_ids[@]} project-lead session(s)"
if [[ $failed -gt 0 ]]; then
  exit 1
fi
