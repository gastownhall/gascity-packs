#!/usr/bin/env bash
# witness-heartbeat-check.sh — deterministic staleness check for witness patrol
# loops. Read-only: it measures, prints, and exits. It never mails, nudges, or
# files warrants — the deacon's health-scan step owns those decisions.
#
# The gap it closes: a witness whose self-scheduled patrol loop has died still
# reports a healthy session state. It sits in `asleep` or `active` forever, so
# the controller's liveness reconcile sees nothing wrong and the deacon's
# LLM health-scan reads the quiet as legitimate idle. Patrol stalls of 14h to
# 63h were observed in production this way with no alert. Heartbeat age is the
# one signal that separates "idle and fine" from "loop is gone", and it is
# exactly the kind of measurement an LLM should not be eyeballing.
#
# For every witness session in a state that implies it should be patrolling
# (active / awake / asleep / running) it takes the NEWER of `last_active` and
# `last_nudge_delivered_at` as the heartbeat and compares its age against
# $GASTOWN_WITNESS_STALE_MIN. Sessions the controller or an operator owns
# (creating / drained / draining / suspended / quarantined / closed) are the
# controller's business and are skipped.
#
# Output: one TSV row per checked witness on stdout, column header on stderr.
#
#   verdict <TAB> rig <TAB> session <TAB> state <TAB> age_seconds <TAB> heartbeat
#
#   fresh        heartbeat inside the window
#   stalled      heartbeat older than the window — the patrol loop is gone
#   no-heartbeat session records no usable timestamp yet (see below)
#   schema-drift session exposes no `last_active` at all — nothing was measured
#
# Exit codes:  0 = every checked witness is fresh (or none to check)
#              1 = findings on stdout (stalled and/or no-heartbeat)
#              2 = the check could not run (bad env, unreadable roster, or a
#                  `gc session list` schema drift that hid `last_active`)
#
# A `no-heartbeat` witness is deliberately NOT reported as stalled. `gc` emits
# the Go zero-time sentinel (0001-01-01T00:00:00Z) for a timestamp it has never
# set, and a naive parse of that turns a brand-new witness into a false stall.
# It is still a finding rather than silence, because an unset heartbeat means
# nothing was measured — it must never read as health.
#
# Env:
#   GC_CITY                    city root (auto-discovered if unset, walks up)
#   GASTOWN_WITNESS_STALE_MIN  staleness window in minutes (default: 90)
#   GASTOWN_WITNESS_ROLE       role suffix to match (default: witness)
#
# Usage:
#   witness-heartbeat-check.sh
#   GASTOWN_WITNESS_STALE_MIN=45 witness-heartbeat-check.sh
#
# The heartbeat-freshness idea comes from gascity-packs PR #99 by
# sarendipitee, which added it as "Check 1b" to a watchdog in the retired
# maintenance pack.

set -euo pipefail

# Resolve city root: env wins, else walk up from cwd looking for city.toml.
if [ -z "${GC_CITY:-}" ]; then
  dir=$(pwd)
  while [ "$dir" != "/" ]; do
    if [ -f "$dir/city.toml" ]; then
      GC_CITY="$dir"
      break
    fi
    dir=$(dirname "$dir")
  done
fi

if [ -z "${GC_CITY:-}" ] || [ ! -f "$GC_CITY/city.toml" ]; then
  echo "witness-heartbeat-check: GC_CITY not set and no city.toml found" >&2
  exit 2
fi

# Default window: the gastown witness does NOT self-schedule a ~60s wakeup — it
# ends its turn with `IDLE:` and the controller's session_sleep policy restarts
# it, bounded by the witness agent's idle_timeout of 1h. 1h is therefore the
# longest legitimate silence for a healthy witness, so the window sits at 1.5x
# that. Well clear of legitimate idle, and still an order of magnitude under the
# 14h floor of the stalls this check exists to catch. Lower it only if your
# city's witness idle_timeout is lower.
STALE_MIN="${GASTOWN_WITNESS_STALE_MIN:-90}"
ROLE="${GASTOWN_WITNESS_ROLE:-witness}"

case "$STALE_MIN" in
  ''|*[!0-9]*)
    echo "witness-heartbeat-check: GASTOWN_WITNESS_STALE_MIN must be a positive integer (got '$STALE_MIN')" >&2
    exit 2
    ;;
esac
if [ "$STALE_MIN" -le 0 ]; then
  echo "witness-heartbeat-check: GASTOWN_WITNESS_STALE_MIN must be a positive integer (got '$STALE_MIN')" >&2
  exit 2
fi

STALE_SECS=$((STALE_MIN * 60))
NOW=$(date -u +%s)

# ts_epoch — RFC3339 timestamp to epoch seconds, printing 0 for "no usable
# signal": empty, null, or the Go zero-time sentinel `gc` emits for a field it
# has never set. 0 means unknown, never "ancient" — parsing 0001-01-01 as a real
# instant is what turns a newly-spawned witness into a false stall.
#
# GNU `date -d` first, BSD `date -j -f` second: the fleet includes macOS.
# Fractional seconds are stripped because `gc` emits them and BSD `date -f`
# cannot parse them.
ts_epoch() {
  local ts="$1" norm epoch
  case "$ts" in
    ''|null|0001-*) printf '0'; return 0 ;;
  esac
  norm=$(printf '%s' "$ts" | sed -E 's/\.[0-9]+(Z|[+-][0-9:]+)?$/\1/')
  epoch=$(date -u -d "$norm" +%s 2>/dev/null) \
    || epoch=$(date -u -j -f '%Y-%m-%dT%H:%M:%S%z' \
                 "$(printf '%s' "$norm" | sed 's/Z$/+0000/')" +%s 2>/dev/null) \
    || epoch=''
  # Anything non-numeric or pre-epoch is another unusable value, not "ancient".
  case "$epoch" in
    ''|*[!0-9]*) printf '0'; return 0 ;;
  esac
  [ "$epoch" -gt 0 ] && printf '%s' "$epoch" || printf '0'
}

# `--state=all` because the default listing hides asleep sessions, and asleep is
# the state a stalled witness parks in.
if ! ROSTER=$(gc session list --state=all --json 2>/dev/null); then
  echo "witness-heartbeat-check: 'gc session list --state=all --json' failed — heartbeat freshness NOT measured" >&2
  exit 2
fi

# `gc session list --json` (schema 1.1.1) returns an OBJECT with a `sessions`
# array. Tolerate a bare top-level array too: that shape shipped previously and
# the schema has drifted before (gc-3tn8g).
JQ_SESSIONS='def sessions_of: (.sessions? // .) | if type == "array" then . else [] end;'

if ! TOTAL=$(printf '%s' "$ROSTER" | jq -r "$JQ_SESSIONS sessions_of | length" 2>/dev/null); then
  echo "witness-heartbeat-check: could not parse the session roster — heartbeat freshness NOT measured" >&2
  exit 2
fi

# Match the role by exact identifier or dot/slash-delimited suffix across every
# identity field a session exposes, so an import binding prefix
# (gastown.witness) or a rig-qualified name (alpha/witness) still matches. Never
# a bare substring — that would catch unrelated names.
ROWS=$(printf '%s' "$ROSTER" | jq -r --arg role "$ROLE" "
  $JQ_SESSIONS
  def is_role(\$r):
    [ (.template // \"\"), (.agent_name // \"\"), (.name // \"\"),
      (.session_name // \"\"), (.alias // \"\") ]
    | map(select(. != \"\"))
    | any(. == \$r or endswith(\".\" + \$r) or endswith(\"/\" + \$r));
  sessions_of
  | .[]
  | select((.closed // false) | not)
  | select(is_role(\$role))
  | [ (if (.name // \"\") != \"\" then .name
       elif (.alias // \"\") != \"\" then .alias
       else (.id // \"?\") end),
      (if (.rig // \"\") != \"\" then .rig else \"-\" end),
      (.state // \"\"),
      (if has(\"last_active\") then \"1\" else \"0\" end),
      ([ (.last_active // \"\"), (.last_nudge_delivered_at // \"\") ]
       | map(select(. != null and . != \"\")) | join(\",\"))
    ]
  | @tsv
" 2>/dev/null) || ROWS=''

printf 'verdict\trig\tsession\tstate\tage_seconds\theartbeat\n' >&2

CHECKED=0
FINDINGS=0
STALLED=0
DRIFTED=0

while IFS=$'\t' read -r ident rig state has_last_active stamps; do
  [ -n "${ident:-}" ] || continue

  case "$(printf '%s' "$state" | tr '[:upper:]' '[:lower:]')" in
    active|awake|asleep|running) ;;
    # creating / drained / draining / suspended / quarantined / archived /
    # closed are controller- or operator-owned. Not this check's business.
    *) continue ;;
  esac

  CHECKED=$((CHECKED + 1))

  if [ "$has_last_active" != "1" ]; then
    DRIFTED=$((DRIFTED + 1))
    printf 'schema-drift\t%s\t%s\t%s\t-\t-\n' "$rig" "$ident" "$state"
    continue
  fi

  # Newest of the available stamps. The patrol loop's self-nudge keeps
  # last_nudge_delivered_at moving, and last_active is often the zero sentinel
  # on an asleep session, so neither field alone is a reliable heartbeat.
  # Compared as epochs rather than sorted as strings so a mixed UTC/offset
  # roster still orders correctly.
  best=0
  best_ts='-'
  saved_ifs=$IFS
  IFS=','
  for ts in ${stamps:-}; do
    IFS=$saved_ifs
    epoch=$(ts_epoch "$ts")
    if [ "$epoch" -gt "$best" ]; then
      best=$epoch
      best_ts=$ts
    fi
    IFS=','
  done
  IFS=$saved_ifs

  if [ "$best" -eq 0 ]; then
    FINDINGS=$((FINDINGS + 1))
    printf 'no-heartbeat\t%s\t%s\t%s\t-\t-\n' "$rig" "$ident" "$state"
    continue
  fi

  age=$((NOW - best))
  # A heartbeat in the future is clock skew, not staleness.
  [ "$age" -lt 0 ] && age=0

  if [ "$age" -ge "$STALE_SECS" ]; then
    STALLED=$((STALLED + 1))
    FINDINGS=$((FINDINGS + 1))
    printf 'stalled\t%s\t%s\t%s\t%s\t%s\n' "$rig" "$ident" "$state" "$age" "$best_ts"
  else
    printf 'fresh\t%s\t%s\t%s\t%s\t%s\n' "$rig" "$ident" "$state" "$age" "$best_ts"
  fi
done <<EOF
$ROWS
EOF

if [ "$DRIFTED" -gt 0 ]; then
  echo "witness-heartbeat-check: $DRIFTED session(s) expose no last_active field — gc session list schema drifted; heartbeat freshness NOT measured" >&2
  exit 2
fi

if [ "$CHECKED" -eq 0 ]; then
  echo "witness-heartbeat-check: no patrolling '$ROLE' session among $TOTAL session(s) — nothing to check" >&2
  exit 0
fi

echo "witness-heartbeat-check: checked $CHECKED '$ROLE' session(s), $STALLED stalled (window ${STALE_MIN}m)" >&2

[ "$FINDINGS" -eq 0 ] || exit 1
