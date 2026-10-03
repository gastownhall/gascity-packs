#!/usr/bin/env bash
#
# has-undelivered-escalates.sh — condition check for escalate-rollups order.
#
# Exits 0 (fire the order) when there is at least one open rollup bead
# with severity:escalate that has not yet been labeled delivered.
# Exits 1 when the query succeeds but finds no work, and 2 when the query
# fails or does not return a JSON list that can be inspected.

set -uo pipefail

query_output=$(gc bd list --label rollup --label severity:escalate --status open --json)
query_status=$?
if [[ "$query_status" -ne 0 ]]; then
  printf 'has-undelivered-escalates: gc bd list failed with exit status %s\n' \
    "$query_status" >&2
  exit 2
fi

count=$(jq -r \
  'if type == "array" then [.[] | select((.labels // []) | index("delivered") | not)] | length else error("expected a JSON array") end' \
  <<<"$query_output")
parse_status=$?
if [[ "$parse_status" -ne 0 ]]; then
  printf 'has-undelivered-escalates: could not parse gc bd list JSON output\n' >&2
  exit 2
fi

# jq exits 0 and prints nothing when handed empty input, so a query that
# succeeded without producing output would otherwise read as "no work".
# An absent count is an unmeasured queue, not an empty one.
if [[ ! "$count" =~ ^[0-9]+$ ]]; then
  printf 'has-undelivered-escalates: gc bd list produced no countable result\n' >&2
  exit 2
fi

if [[ "$count" -gt 0 ]]; then
  exit 0
fi
exit 1
