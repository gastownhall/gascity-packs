#!/usr/bin/env bash
set -euo pipefail

# Post-decompose route-stamp gate: makes decomposed work-units CLAIMABLE.
#
# Decompose creates the implementation convoy's work-unit beads via ad-hoc
# `gc bd create` inside the decompose prompt. That path bypasses the
# formula-graph materializer (which stamps gc.routed_to on graph steps), so the
# work-units land ready with gc.routed_to AND gc.execution_routed_to both empty.
# Pool demand keys EXCLUSIVELY on gc.routed_to, so a routeless work-unit is
# structurally invisible to every pool and sits until a human `gc sling` stamps
# it -- the manual-sling-per-stage tax that makes builds crawl.
#
# This gate closes that gap with a CODED stamp (not "the decomposer agent
# remembers to set it"): it resolves the implementation convoy and the DECLARED
# implementation_target off the workflow root, then stamps
#   gc.routed_to           = <implementation_target>
#   gc.execution_routed_to = <implementation_target>
# on every routeless convoy member -- mirroring the formula-graph stamper
# (internal/dispatch/control.go stamps both keys to `target`). The route is a
# COPIED declared value, not controller judgment (ZFC): implementation_target is
# an authored factory var, exactly what the drain step routes to.
#
# NO-SILENT-FAILURE: after stamping, every member must carry a route. If
# implementation_target is undeclared, or any member stays routeless, this gate
# FAILS LOUDLY (machine-readable stderr, non-zero exit) so the bounded producer
# repair loop surfaces it in gc.attempt_log instead of leaving work-units to sit
# invisibly. This gate never prompts. It is idempotent: an already-routed member
# is left untouched (an explicit route is never clobbered).

fail() {
  echo "route-workunits-check: $*" >&2
  exit 1
}

BEAD_ID="${GC_BEAD_ID:-}"
[ -n "$BEAD_ID" ] || fail "GC_BEAD_ID is required"
command -v gc >/dev/null 2>&1 || fail "gc is required on PATH"
command -v python3 >/dev/null 2>&1 || fail "python3 is required on PATH"

metadata_value() {
  # metadata_value <json> <key> -> prints metadata[key] or empty
  printf '%s' "$1" | python3 -c '
import json
import sys

key = sys.argv[1]
try:
    data = json.load(sys.stdin)
except Exception:
    print("")
    raise SystemExit(0)
if isinstance(data, list):
    data = data[0] if data else {}
if not isinstance(data, dict):
    print("")
    raise SystemExit(0)
metadata = data.get("metadata") or {}
value = metadata.get(key, "") if isinstance(metadata, dict) else ""
print(value if isinstance(value, str) else "")
' "$2"
}

packed_var() {
  # packed_var <root-json> <var-name> -> prints the var from gc.graphv2_vars.v1
  # (the packed runtime-vars JSON object {name: value}), or empty.
  printf '%s' "$1" | python3 -c '
import json
import sys

name = sys.argv[1]
try:
    data = json.load(sys.stdin)
except Exception:
    print("")
    raise SystemExit(0)
if isinstance(data, list):
    data = data[0] if data else {}
if not isinstance(data, dict):
    print("")
    raise SystemExit(0)
metadata = data.get("metadata") or {}
raw = metadata.get("gc.graphv2_vars.v1", "") if isinstance(metadata, dict) else ""
if not isinstance(raw, str) or not raw.strip():
    print("")
    raise SystemExit(0)
try:
    packed = json.loads(raw)
except Exception:
    print("")
    raise SystemExit(0)
value = packed.get(name, "") if isinstance(packed, dict) else ""
print(value if isinstance(value, str) else "")
' "$2"
}

convoy_child_ids() {
  # convoy_child_ids <convoy-status-json> -> prints each child id, one per line
  printf '%s' "$1" | python3 -c '
import json
import sys

try:
    data = json.load(sys.stdin)
except Exception:
    raise SystemExit(0)
if not isinstance(data, dict):
    raise SystemExit(0)
for child in data.get("children") or []:
    if isinstance(child, dict):
        cid = child.get("id", "")
        if isinstance(cid, str) and cid:
            print(cid)
'
}

SHOW_JSON="$(gc bd show "$BEAD_ID" --json 2>/dev/null)" || fail "gc bd show $BEAD_ID failed"

ROOT_ID="$(metadata_value "$SHOW_JSON" "gc.root_bead_id")"
ROOT_JSON="$SHOW_JSON"
if [ -n "$ROOT_ID" ] && [ "$ROOT_ID" != "$BEAD_ID" ]; then
  ROOT_JSON="$(gc bd show "$ROOT_ID" --json 2>/dev/null)" || fail "gc bd show $ROOT_ID failed"
fi
ROOT_LABEL="${ROOT_ID:-$BEAD_ID}"

CONVOY_ID="$(metadata_value "$ROOT_JSON" "gc.build.implementation_convoy_id")"
[ -n "$CONVOY_ID" ] || CONVOY_ID="$(metadata_value "$ROOT_JSON" "gc.input_convoy_id")"
[ -n "$CONVOY_ID" ] || fail "no implementation convoy recorded on root $ROOT_LABEL (gc.build.implementation_convoy_id and gc.input_convoy_id both empty); decompose must record the convoy before work-units can be routed"

TARGET="$(metadata_value "$ROOT_JSON" "gc.var.implementation_target")"
[ -n "$TARGET" ] || TARGET="$(packed_var "$ROOT_JSON" "implementation_target")"
[ -n "$TARGET" ] || fail "no implementation_target declared on root $ROOT_LABEL (gc.var.implementation_target and gc.graphv2_vars.v1 both empty); cannot route decomposed work-units -- they would sit unclaimable"

CONVOY_JSON="$(gc convoy status "$CONVOY_ID" --json 2>/dev/null)" || fail "gc convoy status $CONVOY_ID failed"
MEMBERS="$(convoy_child_ids "$CONVOY_JSON")"

TOTAL=0
STAMPED=0
while IFS= read -r member; do
  [ -n "$member" ] || continue
  TOTAL=$((TOTAL + 1))
  MEMBER_JSON="$(gc bd show "$member" --json 2>/dev/null)" || fail "gc bd show $member failed"
  ROUTE="$(metadata_value "$MEMBER_JSON" "gc.routed_to")"
  if [ -z "$ROUTE" ]; then
    gc bd update "$member" \
      --set-metadata "gc.routed_to=$TARGET" \
      --set-metadata "gc.execution_routed_to=$TARGET" >/dev/null 2>&1 \
      || fail "failed to stamp gc.routed_to=$TARGET on work-unit $member"
    STAMPED=$((STAMPED + 1))
  fi
done <<EOF
$MEMBERS
EOF

if [ "$TOTAL" -eq 0 ]; then
  # Decompose is contracted to never create an empty implementation convoy; a
  # zero-member convoy is the decomposition artifact gate's concern, not this
  # gate's. Nothing to route -- pass without inventing a failure.
  echo "route-workunits: convoy=$CONVOY_ID target=$TARGET members=0 (nothing to route)"
  exit 0
fi

# NO-SILENT-FAILURE verify: re-read every member; each must now carry a route.
UNROUTED=""
while IFS= read -r member; do
  [ -n "$member" ] || continue
  MEMBER_JSON="$(gc bd show "$member" --json 2>/dev/null)" || fail "gc bd show $member failed"
  ROUTE="$(metadata_value "$MEMBER_JSON" "gc.routed_to")"
  [ -n "$ROUTE" ] || UNROUTED="$UNROUTED $member"
done <<EOF
$MEMBERS
EOF
[ -z "$UNROUTED" ] || fail "work-units remain routeless after stamping (would sit unclaimable, invisible to every pool):$UNROUTED"

echo "route-workunits: convoy=$CONVOY_ID target=$TARGET members=$TOTAL stamped=$STAMPED (all claimable)"
exit 0
