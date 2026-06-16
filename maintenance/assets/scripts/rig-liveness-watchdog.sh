#!/usr/bin/env bash
# rig-liveness-watchdog — deterministic per-rig agent + merge-freshness watchdog.
#
# Catches the failure where a critical rig agent (refinery / witness) silently
# dies, or the refinery stalls with a REAL merge backlog, with NO alert. This is
# a plain exec order (no LLM, no agent, no wisp) precisely BECAUSE the Witness
# LLM patrol loop is the thing that silently dies — a deterministic shell tick
# survives where an agent loop does not.
#
# RIG SCOPING. The controller fans every exec order out once per scope (the HQ /
# global scope plus one scope per rig) and stamps $GC_RIG with the scope's rig
# name — empty for the HQ/global scope. The sibling store/exec env builder
# (gascity internal/orders/env.go reserves GC_RIG; cmd/gc/store_target_exec.go
# sets env["GC_RIG"]=target.RigName per scope). So this script checks ONLY the
# single rig named in $GC_RIG and does NOT loop every rig itself. The bare
# global scope (GC_RIG empty) is a no-op — it exits immediately so the per-rig
# fan-out is the single source of one-invocation-per-rig, with no global
# duplicate racing the per-rig runs. The ledger filename includes the rig name
# so concurrent rig scopes never write the same file.
#
# For the rig it is invoked for it checks:
#
#   1. The rig's `refinery` and `witness` sessions are alive. A session is
#      DEAD when it is missing entirely or its state is one of the hard-dead
#      states (crashed / creating / failed-create / closed). `asleep`,
#      `active`, `awake`, `running` are all ALIVE (an idle refinery sleeps).
#
#   1b. Witness heartbeat freshness. A witness in an ALIVE state can still have
#      a silently-dead self-scheduled patrol loop — it just sits `asleep`
#      forever. The chronic real failure (patrol stalls of 14h-63h, all while
#      "asleep"/"active") is invisible to the dead-state check above. So we also
#      treat an ALIVE witness whose last-active heartbeat is older than
#      $WATCHDOG_WITNESS_STALE_MIN minutes as STALLED. A healthy witness sleeps
#      ~60s between patrol cycles, so >15 min of silence means the loop is dead.
#
#   2. Refinery health: a refinery in a hard-dead state (crashed / creating /
#      failed-create / closed / missing) is ALWAYS an incident, regardless of
#      queue depth — a crashed refinery is never normal.
#
#   2b. Merge-stall, gated on a REAL routed-bead backlog. An idle/asleep
#      refinery on a quiet dev rig is normal: low-activity rigs legitimately
#      leave beads assigned to a sleeping refinery for hours with no merge. That
#      is NOT a stall. We raise a merge-stall ONLY when the refinery's routed
#      merge queue holds at least $WATCHDOG_MIN_QUEUE genuinely-ready beads AND
#      no merge has landed on the default branch inside $WATCHDOG_FRESH_MIN
#      minutes. Freshness is measured against origin/<default> (the real merge
#      target) when a remote-tracking ref exists, falling back to the local ref.
#      Counting local feature branches is DELIBERATELY NOT a backlog signal:
#      stale/abandoned/squash-merged branches accumulate forever on dev rigs and
#      `git --no-contains` cannot see squash-merges, so branch-counting produced
#      chronic phantom backlogs (an idle rig with a queue of 1 but 16 dead local
#      branches was wrongly flagged as stalled). The routed-bead queue is the
#      authoritative pressure signal; unmerged-branch count is evidence only.
#
# On any detected dead-agent or stall it mails a LOUD [INCIDENT] escalation to
# $WATCHDOG_ESCALATE_TO (default: mayor) with concrete evidence. A JSON ledger
# de-dups two ways: (a) a hard wall-clock cooldown — a given (rig, incident-type)
# re-alerts at most once per $WATCHDOG_COOLDOWN_MIN minutes, mirroring the
# per-key cooldown in nudge-on-mail.sh; (b) within the cooldown the symptom is
# silently re-counted, never re-mailed, so a persistent incident does not spam.
#
# Config (all env-overridable, upstream-friendly defaults):
#   WATCHDOG_ESCALATE_TO   recipient for incident mail        (default: mayor)
#   WATCHDOG_FRESH_MIN     merge-freshness window, minutes    (default: 60)
#   WATCHDOG_COOLDOWN_MIN  min minutes between re-alerts of the same
#                          (rig, incident-type)               (default: 45)
#   WATCHDOG_WITNESS_STALE_MIN witness heartbeat staleness, minutes (default: 30)
#   WATCHDOG_STARTUP_GRACE_MIN how long a transient 'creating' / startup state is
#                          tolerated before it counts as dead  (default: 10)
#   WATCHDOG_MIN_QUEUE     minimum routed merge-queue depth to call a merge-stall
#                          (default: 2) — below this, an idle refinery is treated
#                          as quiet, not stalled. The dead/crashed-refinery
#                          escalation is UNGATED by this threshold.
set -euo pipefail

# Trace bd/gc invocations to $GC_BD_TRACE_JSON when set (no-op otherwise).
__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "$__SCRIPT_DIR/_bd_trace.sh" "rig-liveness-watchdog"

# Rig scope. Empty GC_RIG is the HQ/global scope: this watchdog only patrols
# rigs, so the global instance is a deliberate no-op. The per-rig fan-out is
# what gives exactly one invocation per rig.
RIG="${GC_RIG:-}"
[ -n "$RIG" ] || exit 0

ESCALATE_TO="${WATCHDOG_ESCALATE_TO:-mayor}"
FRESH_MIN="${WATCHDOG_FRESH_MIN:-60}"
COOLDOWN_MIN="${WATCHDOG_COOLDOWN_MIN:-45}"
WITNESS_STALE_MIN="${WATCHDOG_WITNESS_STALE_MIN:-30}"
STARTUP_GRACE_MIN="${WATCHDOG_STARTUP_GRACE_MIN:-10}"
MIN_QUEUE="${WATCHDOG_MIN_QUEUE:-2}"

CITY="${GC_CITY:-.}"
PACK_STATE_DIR="${GC_PACK_STATE_DIR:-${GC_CITY_RUNTIME_DIR:-$CITY/.gc/runtime}/packs/maintenance}"
# Per-rig ledger: GC_PACK_STATE_DIR is per-pack, not per-rig, so every rig scope
# would otherwise contend on one ledger file. Slugging the rig name into the
# filename gives each concurrent scope its own file. (A-Z a-z 0-9 . _ - kept;
# everything else collapses to '_' so the name is filesystem-safe.)
RIG_SLUG=$(printf '%s' "$RIG" | tr -c 'A-Za-z0-9._-' '_')
LEDGER="$PACK_STATE_DIR/rig-liveness-incidents-$RIG_SLUG.json"
mkdir -p "$PACK_STATE_DIR"
[ -f "$LEDGER" ] || echo '{}' > "$LEDGER"

NOW=$(date +%s)
FRESH_SECS=$((FRESH_MIN * 60))
WITNESS_STALE_SECS=$((WITNESS_STALE_MIN * 60))
COOLDOWN_SECS=$((COOLDOWN_MIN * 60))
STARTUP_GRACE_SECS=$((STARTUP_GRACE_MIN * 60))

# ts_epoch — parse an RFC3339 timestamp to epoch seconds, returning 0 for an
# empty value or the Go zero-time sentinel (0001-01-01T00:00:00Z) that gc emits
# for a session that has not recorded that field yet. A 0 result means "no
# usable signal" — never "ancient".
ts_epoch() {
    local ts="$1"
    case "$ts" in
        ""|null|0001-01-01T00:00:00Z|0001-*) printf '0'; return 0 ;;
    esac
    local e
    e=$(date -u -d "$ts" +%s 2>/dev/null) || { printf '0'; return 0; }
    # Guard against any other pre-epoch/sentinel value slipping through.
    [ "$e" -gt 0 ] 2>/dev/null && printf '%s' "$e" || printf '0'
}

# normalize_sessions — tolerate both the v1.1.1 object shape
# ({filters,ok,schema_version,sessions,summary}) and the OLD flat top-level
# array. `(.sessions? // .)` yields the array in both cases; `arrays` then
# only passes through when the result really is an array, so a scalar/object
# never errors or leaks a non-session row.
SESSIONS_JQ='(.sessions? // .) | if type == "array" then . else [] end'

# Hard-dead session states: missing maps to "absent" below; these are the
# states that mean a present session is not doing useful work and will not
# recover on its own. NOTE: 'creating' is intentionally NOT here — a session
# mid-startup is transient and routinely flickers through 'creating' for a few
# seconds on a fresh spawn or rig restart. Treating it as instant-dead caused
# false "[INCIDENT] witness/refinery creating" spam. It is handled via the
# startup-grace path (is_startup_state) instead.
is_dead_state() {
    case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
        crashed|failed-create|failed_create|closed) return 0 ;;
        *) return 1 ;;
    esac
}

# Transient startup/in-progress states. A session sitting in one of these for
# longer than the startup grace window is treated as a genuinely stuck spawn;
# inside the window it is healthy mid-startup and must not alert.
is_startup_state() {
    case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
        creating|starting|initializing) return 0 ;;
        *) return 1 ;;
    esac
}

# Ledger shape. Each key maps to an object { c, t, f }:
#   c  total times this incident has been observed (diagnostic)
#   t  epoch of the last mail actually SENT for this incident (cooldown clock)
#   f  epoch this incident was FIRST observed in the current streak (used by the
#      startup-grace window so a 'creating' state must persist before it alerts)
# Legacy ledgers stored a bare integer count; ledger_* readers coerce that to a
# count with absent timestamps so an upgrade does not crash or lose dedup.
COUNTS=$(cat "$LEDGER" 2>/dev/null || printf '{}')
printf '%s' "$COUNTS" | jq -e 'type == "object"' >/dev/null 2>&1 || COUNTS='{}'
INCIDENTS=0
declare -A SEEN_KEYS=()

# ledger_last_alert KEY — epoch of the last mail sent for KEY (0 if none).
ledger_last_alert() {
    printf '%s' "$COUNTS" | jq -r --arg k "$1" \
        '(.[$k] | if type=="object" then (.t // 0) else 0 end) // 0' 2>/dev/null || printf '0'
}

# ledger_first_seen KEY — epoch this incident streak began. Lazily stamps NOW
# the first tick a streak is seen and returns it, so repeated calls within a
# streak return the original first-seen epoch (the grace-window anchor).
ledger_first_seen() {
    local key="$1" f
    f=$(printf '%s' "$COUNTS" | jq -r --arg k "$key" \
        '(.[$k] | if type=="object" then (.f // 0) else 0 end) // 0' 2>/dev/null) || f=0
    if [ "${f:-0}" -le 0 ] 2>/dev/null; then
        f=$NOW
        COUNTS=$(printf '%s' "$COUNTS" | jq --arg k "$key" --argjson f "$f" \
            '.[$k] = ((.[$k] | if type=="object" then . else {} end) + {f:$f})' 2>/dev/null) || true
    fi
    printf '%s' "$f"
}

# mark_seen KEY — record that this incident streak is live this tick (so the
# prune at the end keeps it) without sending mail or resetting cooldown.
mark_seen() {
    local key="$1"
    SEEN_KEYS["$key"]=1
    COUNTS=$(printf '%s' "$COUNTS" | jq --arg k "$key" --argjson n "$NOW" \
        '.[$k] = ((.[$k] | if type=="object" then . else {} end)
                  + {c: (((.[$k] // {}) | if type=="object" then (.c // 0) else (.[$k] // 0) end) + 1)}
                  + (if ((.[$k] // {}) | type=="object" and (.f // 0) > 0) then {} else {f:$n} end))' 2>/dev/null) || true
}

# escalate — emit a [INCIDENT] mail, hard rate-limited by a per-key wall-clock
# cooldown. Args: $1 incident key (rig:agent:symptom-class), $2 subject, $3 body
escalate() {
    local key="$1" subject="$2" body="$3"
    local last age
    SEEN_KEYS["$key"]=1
    last=$(ledger_last_alert "$key")
    age=$((NOW - last))
    # Within the cooldown window since the last actual mail: re-count, no re-mail.
    if [ "${last:-0}" -gt 0 ] 2>/dev/null && [ "$age" -lt "$COOLDOWN_SECS" ]; then
        mark_seen "$key"
        return 0
    fi
    if ! gc mail send "$ESCALATE_TO" -s "$subject" -m "$body" 2>/dev/null; then
        echo "rig-liveness-watchdog[$RIG]: WARNING: gc mail send failed for key '$key'; incident counted but cooldown not advanced" >&2
        mark_seen "$key"
        return 0
    fi
    INCIDENTS=$((INCIDENTS + 1))
    SEEN_KEYS["$key"]=1
    # Stamp last-alert epoch and bump count; preserve/establish first-seen.
    COUNTS=$(printf '%s' "$COUNTS" | jq --arg k "$key" --argjson n "$NOW" \
        '.[$k] = ((.[$k] | if type=="object" then . else {} end)
                  + {t:$n}
                  + {c: (((.[$k] // {}) | if type=="object" then (.c // 0) else (.[$k] // 0) end) + 1)}
                  + (if ((.[$k] // {}) | type=="object" and (.f // 0) > 0) then {} else {f:$n} end))' 2>/dev/null) || true
}

# Resolve this rig's path + default branch from the registry. Scoped to $RIG so
# we touch only the single rig the controller invoked us for.
RIG_JSON=$(gc rig list --json 2>/dev/null) || exit 0
[ -n "$RIG_JSON" ] || exit 0

read -r rig_path default_branch is_running < <(printf '%s' "$RIG_JSON" | jq -r --arg rig "$RIG" '
    .rigs[]
    | select(.hq == false)
    | select(.name == $rig)
    | "\(.path // "")\t\(.default_branch // "")\t\(if (.suspended == false and .running == true) then "yes" else "no" end)"' 2>/dev/null | head -1 | tr '\t' ' ')

# Skip a suspended / non-running rig: an intentionally suspended dev rig has no
# live agents to watch, so its sleeping refinery/witness are expected.
[ "${is_running:-no}" = "yes" ] || exit 0

# Pull this rig's sessions once; tolerate both JSON shapes.
sess=$(gc --rig "$RIG" session list --json 2>/dev/null) || sess=""
[ -n "$sess" ] || sess='[]'

# State of the named role's session, or "absent" if no such session.
role_state() {
    local role="$1"
    printf '%s' "$sess" | jq -r --arg role "$role" "
        [ $SESSIONS_JQ
          | .[]
          | select(((.name // \"\") | test(\"\\\\.\" + \$role + \"\$\"))
                   or ((.agent_name // \"\") | test(\"\\\\.\" + \$role + \"\$\"))
                   or ((.role // \"\") | test(\"\\\\.\" + \$role + \"\$\"))) ]
        | (.[0].state // \"absent\")
    " 2>/dev/null || printf 'absent'
}

# role_heartbeat — newest heartbeat timestamp string for the named role,
# taken as the max of last_active / last_nudge_delivered_at (the patrol
# loop's self-nudge keeps last_nudge_delivered_at fresh; last_active is the
# zero sentinel for an asleep session). Empty string when the role is absent
# or exposes no usable timestamp.
role_heartbeat() {
    local role="$1"
    printf '%s' "$sess" | jq -r --arg role "$role" "
        [ $SESSIONS_JQ
          | .[]
          | select(((.name // \"\") | test(\"\\\\.\" + \$role + \"\$\"))
                   or ((.agent_name // \"\") | test(\"\\\\.\" + \$role + \"\$\"))
                   or ((.role // \"\") | test(\"\\\\.\" + \$role + \"\$\"))) ]
        | .[0]
        | [ (.last_active // empty), (.last_nudge_delivered_at // empty) ]
        | map(select(. != null and . != \"\" and (startswith(\"0001-\") | not)))
        | sort
        | (last // \"\")
    " 2>/dev/null || printf ''
}

witness_state=$(role_state witness)
refinery_state=$(role_state refinery)
[ -n "$witness_state" ] || witness_state="absent"
[ -n "$refinery_state" ] || refinery_state="absent"

# startup_grace_exceeded KEY — for a transient startup state, true only
# once the streak has persisted past the grace window; otherwise records the
# streak as seen (so the ledger entry survives pruning) and returns false so the
# session is left alone mid-startup.
startup_grace_exceeded() {
    local key="$1" first age
    first=$(ledger_first_seen "$key")
    age=$((NOW - first))
    if [ "$age" -ge "$STARTUP_GRACE_SECS" ]; then
        return 0
    fi
    mark_seen "$key"
    return 1
}

# --- Check 1: witness must be alive (it never legitimately sleeps off). ---
if is_startup_state "$witness_state" && ! startup_grace_exceeded "$RIG:witness:dead"; then
    : # witness mid-startup within grace window — not an incident yet.
elif is_dead_state "$witness_state" || is_startup_state "$witness_state"; then
    symptom="$witness_state"
    [ "$symptom" = "" ] && symptom="missing"
    escalate "$RIG:witness:dead" \
        "[INCIDENT] rig $RIG: witness $symptom" \
        "Watchdog tick $(date -u +%Y-%m-%dT%H:%M:%SZ): the witness session for rig '$RIG' is $symptom.
The witness LLM patrol loop is not alive and will not self-recover.

Evidence:
  rig            = $RIG
  witness state  = $witness_state
  refinery state = $refinery_state
  default branch = $default_branch

Action: gc session reset $RIG/<witness-alias>  (or respawn the rig witness)."
else
    # --- Check 1b: ALIVE witness with a stalled (dead) patrol loop. ---
    # Distinct symptom-class (:witness:stalled) from :witness:dead so de-dup
    # treats them as separate incidents.
    hb=$(role_heartbeat witness)
    hb_epoch=$(ts_epoch "$hb")
    if [ "$hb_epoch" -gt 0 ]; then
        hb_age=$((NOW - hb_epoch))
        if [ "$hb_age" -ge "$WITNESS_STALE_SECS" ]; then
            escalate "$RIG:witness:stalled" \
                "[INCIDENT] rig $RIG: witness stalled (last active $((hb_age / 60))m ago)" \
                "Watchdog tick $(date -u +%Y-%m-%dT%H:%M:%SZ): the witness session for rig '$RIG' is in an alive state ('$witness_state') but its self-scheduled patrol loop has gone silent.

A healthy witness sleeps ~60s between patrol cycles, so a heartbeat this old means
the ScheduleWakeup loop has silently died — the witness is alive but not patrolling.

Evidence:
  rig            = $RIG
  witness state  = $witness_state
  last heartbeat = $hb ($((hb_age / 60)) min ago, threshold $WITNESS_STALE_MIN min)
  refinery state = $refinery_state
  default branch = $default_branch

Action: nudge / gc session reset $RIG/<witness-alias> to restart the patrol loop."
        fi
    fi
fi

# --- Check 2: refinery dead-state OR merge-freshness stall. ---
# Merge queue depth: open/in_progress beads assigned to the refinery, plus
# ready in_progress work that still needs to merge.
queue=$(gc bd list --rig "$RIG" --json --limit=0 2>/dev/null \
    | jq '[ .[]
            | select((.assignee // "") | test("refinery"))
            | select(.status == "open" or .status == "in_progress")
            | select((.ephemeral // false) != true) ] | length' 2>/dev/null) || queue=0
[ -n "$queue" ] || queue=0

# Last merge: last commit time on the rig's merge TARGET. The refinery merges
# into origin/<default-branch>, so freshness must be measured against the
# remote-tracking ref, not the local default ref (which a quiet dev rig can leave
# stale for hours even while origin advances). Prefer origin/<default>; fall back
# to the local ref only when no remote-tracking ref exists. Missing repo/branch
# yields 0 (unknown) and is treated as "no recent merge".
last_merge=0
merge_ref=""
if [ -n "$rig_path" ] && [ -n "$default_branch" ] && [ -d "$rig_path/.git" ]; then
    if git -C "$rig_path" rev-parse --verify --quiet "refs/remotes/origin/$default_branch" >/dev/null 2>&1; then
        merge_ref="origin/$default_branch"
    elif git -C "$rig_path" rev-parse --verify --quiet "refs/heads/$default_branch" >/dev/null 2>&1; then
        merge_ref="$default_branch"
    fi
    if [ -n "$merge_ref" ]; then
        last_merge=$(git -C "$rig_path" log -1 --format='%ct' "$merge_ref" 2>/dev/null) || last_merge=0
    fi
fi
[ -n "$last_merge" ] || last_merge=0
age=$((NOW - last_merge))
[ "$last_merge" -eq 0 ] && age=-1

# unmerged_branches — count local feature branches NOT yet contained in
# origin/<default>. EVIDENCE ONLY: this is reported in incident mail but does
# NOT gate the stall. `git --no-contains` cannot detect squash-merges, and stale
# / abandoned branches pile up on dev rigs forever, so a non-zero count here is
# NOT proof of backlog — using it as a stall trigger produced chronic phantom
# merge-stall alerts on idle rigs. The routed-bead queue is the only authority.
unmerged_branches=0
if [ -n "$merge_ref" ]; then
    unmerged_branches=$(git -C "$rig_path" for-each-ref --format='%(refname:short)' \
        --no-contains "$merge_ref" refs/heads/ 2>/dev/null \
        | grep -vxF "$default_branch" | grep -c . 2>/dev/null) || unmerged_branches=0
fi
[ -n "$unmerged_branches" ] || unmerged_branches=0

# A REAL backlog is the routed merge queue at/above the threshold. Branch count
# is deliberately excluded (see above). Below-threshold queue = quiet idle rig,
# NOT a stall, no matter how many dead local branches linger.
real_backlog=no
if [ "$queue" -ge "$MIN_QUEUE" ]; then
    real_backlog=yes
fi

if is_startup_state "$refinery_state" && ! startup_grace_exceeded "$RIG:refinery:dead"; then
    : # refinery mid-startup within grace window — not an incident yet.
elif is_dead_state "$refinery_state" || is_startup_state "$refinery_state"; then
    # Dead/crashed refinery is ALWAYS an incident — ungated by the backlog
    # threshold. A crashed refinery is never normal even with an empty queue.
    symptom="$refinery_state"
    [ "$symptom" = "" ] && symptom="missing"
    escalate "$RIG:refinery:dead" \
        "[INCIDENT] rig $RIG: refinery $symptom" \
        "Watchdog tick $(date -u +%Y-%m-%dT%H:%M:%SZ): the refinery session for rig '$RIG' is $symptom.

Evidence:
  rig             = $RIG
  refinery state  = $refinery_state
  merge queue     = $queue bead(s)
  unmerged branch = $unmerged_branches
  last merge (s)  = $age ago on '$default_branch'
  default branch  = $default_branch

Action: investigate / gc session reset $RIG/<refinery-alias>."
elif [ "$real_backlog" = "yes" ] && { [ "$last_merge" -eq 0 ] || [ "$age" -ge "$FRESH_SECS" ]; }; then
    # Stall: an alive-but-idle refinery sitting on a REAL routed-bead backlog
    # (queue at/above WATCHDOG_MIN_QUEUE) with no merge to the merge target inside
    # the freshness window. A sub-threshold queue on a quiet dev rig fails the
    # real_backlog test above and is correctly ignored, no matter how many stale
    # local branches exist.
    if [ "$last_merge" -eq 0 ]; then
        mergeline="unknown (no commit found on '${merge_ref:-$default_branch}')"
    else
        mergeline="$((age / 60)) min ago on '$merge_ref' (window: $FRESH_MIN min)"
    fi
    escalate "$RIG:refinery:stall" \
        "[INCIDENT] rig $RIG: refinery merge-stall" \
        "Watchdog tick $(date -u +%Y-%m-%dT%H:%M:%SZ): rig '$RIG' has a real merge backlog but no merge inside the freshness window.

Evidence:
  rig             = $RIG
  refinery state  = $refinery_state
  merge queue     = $queue bead(s) routed to refinery / ready (threshold $MIN_QUEUE)
  unmerged branch = $unmerged_branches feature branch(es) not in '$default_branch'
  last merge      = $mergeline
  default branch  = $default_branch

The refinery is not draining the queue. Action: check the refinery session,
its current verification, and the default-branch gate state."
fi

# Prune ledger keys for incidents that did NOT recur this tick (streak cleared),
# so first-seen grace anchors and cooldown clocks reset when a rig recovers.
# Whole object values (c/t/f) are carried forward for surviving keys.
PRUNED='{}'
while IFS= read -r k; do
    [ -z "$k" ] && continue
    if [ -n "${SEEN_KEYS[$k]:-}" ]; then
        PRUNED=$(printf '%s' "$PRUNED" | jq --arg k "$k" --argjson src "$COUNTS" \
            '.[$k] = ($src[$k] // {})' 2>/dev/null) || true
    fi
done < <(printf '%s' "$COUNTS" | jq -r 'keys[]' 2>/dev/null)
COUNTS="$PRUNED"

_ledger_tmp="$LEDGER.tmp.$$"
printf '%s' "$COUNTS" > "$_ledger_tmp"
mv -f "$_ledger_tmp" "$LEDGER"

if [ "$INCIDENTS" -gt 0 ]; then
    echo "rig-liveness-watchdog[$RIG]: escalated $INCIDENTS incident(s)"
fi
