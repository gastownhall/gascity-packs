#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
SCRIPT="$ROOT/gastown/assets/scripts/polecat-churn-watcher.sh"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

write_gc_stub() {
    local bin="$1"
    mkdir -p "$bin"
    cat >"$bin/gc" <<'SH'
#!/usr/bin/env sh
# Only `gc --rig <rig> bd list --status=open --json` is exercised here.
case "$*" in
    *"bd list"*"--json"*) cat "$GC_BEADS_JSON" ;;
    *) printf '[]' ;;
esac
SH
    chmod +x "$bin/gc"
}

test_exact_session_match_is_churn_and_handoff_is_not() {
    local tmp city bin beads pollers logdir
    tmp=$(mktemp -d)
    city="$tmp/city"
    bin="$tmp/bin"
    beads="$tmp/beads.json"
    pollers="$city/.gc/nudges/pollers"
    logdir="$tmp/logs"
    mkdir -p "$city" "$pollers" "$logdir"
    : >"$city/city.toml"
    write_gc_stub "$bin"

    # A dead session's churned claim (open + unassigned + exact polecat_session),
    # a normal refinery handoff (open but assigned — must be excluded), a live
    # session's bead, and a bead whose work_dir merely contains the dead session
    # name as a substring (must NOT false-positive under exact-match keying).
    cat >"$beads" <<'JSON'
[
  {"id":"churn-1","assignee":"","metadata":{"polecat_session":"deadsess"}},
  {"id":"handoff-1","assignee":"refinery","metadata":{"polecat_session":"deadsess","work_dir":"/w/deadsess"}},
  {"id":"live-1","assignee":"","metadata":{"polecat_session":"othersess"}},
  {"id":"substr-1","assignee":"","metadata":{"work_dir":"/w/deadsess/wt"}}
]
JSON

    # Tick 1: the dead session is still live (pid file present). Seeds the state
    # file so tick 2 can observe the disappearance.
    : >"$pollers/polecat-deadsess.pid"
    GC_CITY="$city" GC_RIG="helm" LOG_DIR="$logdir" \
        GC_BEADS_JSON="$beads" PATH="$bin:$PATH" bash "$SCRIPT"

    # Tick 2: the pid file is gone -> the session disappeared.
    rm -f "$pollers/polecat-deadsess.pid"
    GC_CITY="$city" GC_RIG="helm" LOG_DIR="$logdir" \
        GC_BEADS_JSON="$beads" PATH="$bin:$PATH" bash "$SCRIPT"

    local log="$logdir/polecat-churn.log"
    [[ -f "$log" ]] || fail "churn watcher wrote no log"
    grep -F '"event":"polecat_killed_mid_claim"' "$log" >/dev/null ||
        fail "exact metadata.polecat_session match was not detected as churn"
    grep -F '"bead":"churn-1"' "$log" >/dev/null ||
        fail "the churned claim bead was not reported"
    ! grep -F 'handoff-1' "$log" >/dev/null ||
        fail "a refinery-handoff bead (assigned) was wrongly flagged as churn"
    ! grep -F 'live-1' "$log" >/dev/null ||
        fail "a different live session's bead was wrongly flagged"
    ! grep -F 'substr-1' "$log" >/dev/null ||
        fail "a work_dir substring match wrongly false-positived as churn"
}

test_exact_session_match_is_churn_and_handoff_is_not

echo "polecat churn watcher tests passed"
