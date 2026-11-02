#!/usr/bin/env bash
set -euo pipefail

# Executed coverage for the witness liveness map (mol-witness-patrol,
# recover-orphaned-beads Step 1).
#
# The map resolves a work bead's assignee to the state of the session that
# owns it, keyed on every identifier an assignee may take (id, name,
# session_name, alias, agent_name, and a session bead's
# configured_named_identity). `archived`, `closed` and `absent` mean the
# owner is gone, and the witness then salvages the bead's worktree, deletes
# it, and returns the bead to the pool.
#
# `gc session list --state=all` lists closed sessions too (Gas City 1.6 on
# every route; the city API since gascity#8209). A closed row keeps the
# alias, agent_name and name of the session it belonged to, and rows come
# newest-first. The map used to let the last row win, so an older closed
# session that shared a live polecat's alias overwrote the live entry with
# "closed", and the live polecat's work was salvaged and reset under it.
# Closed session beads (from `gc bd list --all`) keep configured_named_identity
# and could do the same through the bead leg.
#
# The blocks are LIFTED out of the formula and executed, not transcribed.
# Point WITNESS_LIVENESS_ROOT at another tree to run this file unmodified
# against it (the red control).

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
TREE="${WITNESS_LIVENESS_ROOT:-$ROOT}"
FORMULA="$TREE/gastown/formulas/mol-witness-patrol.toml"

command -v jq >/dev/null 2>&1 || {
    echo "FAIL: jq is required (the lifted blocks parse the stub's JSON with real jq)" >&2
    exit 1
}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

BIN="$tmp/bin"
MAP_BLOCK="$tmp/liveness-map.sh"
RESOLVE_BLOCK="$tmp/resolve.sh"
FAILSAFE_BLOCK="$tmp/fail-safe.sh"
GC_LOG="$tmp/gc.log"
OUT="$tmp/out.log"
export GC_LOG

fail() {
    echo "FAIL: $*" >&2
    if [ -s "$OUT" ]; then
        echo "--- captured block output ---" >&2
        tail -n 20 "$OUT" >&2
    fi
    exit 1
}

# lift_block <sentinel> <dest>: the fenced ```bash block containing <sentinel>.
lift_block() {
    local sentinel="$1" dest="$2"
    awk -v want="$sentinel" '
        /^[[:space:]]*```bash[[:space:]]*$/ { inblk = 1; body = ""; next }
        inblk && /^[[:space:]]*```[[:space:]]*$/ {
            inblk = 0
            if (index(body, want)) { printf "%s", body; found = 1 }
            body = ""
            next
        }
        inblk { body = body $0 "\n"; next }
        END { exit(found ? 0 : 1) }
    ' "$FORMULA" >"$dest" || fail "no fenced bash block in $FORMULA contains: $sentinel"
    [ -s "$dest" ] || fail "lifted an empty block for: $sentinel"
    bash -n "$dest" || fail "lifted block does not parse: $sentinel"
}

lift_block 'LIVENESS_MAP=$(jq -n' "$MAP_BLOCK"
lift_block '.[$a] // "absent"' "$RESOLVE_BLOCK"
lift_block 'FAIL-SAFE: empty liveness map' "$FAILSAFE_BLOCK"

mkdir -p "$BIN"
cat >"$BIN/gc" <<'SH'
#!/usr/bin/env sh
# Patterns read as `gc bd ...`, which tests/test_no_bare_bd_commands.py accepts.
invocation="gc $*"
printf '%s\n' "$invocation" >>"$GC_LOG"
case "$invocation" in
    *"gc session list"*) cat "$GC_SESSIONS_JSON" ;;
    *"gc bd list"*) cat "$GC_SESSION_BEADS_JSON" ;;
    *"gc mail send"*) : ;;
    *) printf '{}' ;;
esac
SH
chmod +x "$BIN/gc"

export PATH="$BIN:$PATH"
export GC_SESSIONS_JSON="$tmp/sessions.json"
export GC_SESSION_BEADS_JSON="$tmp/session-beads.json"

set_roster() { printf '%s' "$1" >"$GC_SESSIONS_JSON"; }
set_session_beads() { printf '%s' "$1" >"$GC_SESSION_BEADS_JSON"; }

# resolve <assignee>: build the map with the shipped block, then resolve the
# assignee with the shipped lookup, in a plain `set +eu` shell like the agent's.
resolve() {
    STATE=$(
        set +eu
        ASSIGNEE="$1"
        { . "$MAP_BLOCK"; . "$RESOLVE_BLOCK"; } >"$OUT" 2>&1
        printf '%s' "$STATE"
    )
}

assert_state() {
    local assignee="$1" want="$2" label="$3"
    resolve "$assignee"
    [ "$STATE" = "$want" ] || fail "$label: $assignee resolved to '$STATE', want '$want'"
}

# Gas City 1.6 `gc session list --state=all --json`: newest first, a closed
# row has state "closed" and closed true, a never-active last_active is "".
LIVE_ROW='{"id":"gc-20","name":"rig/gastown.furiosa","template":"rig/gastown.polecat","state":"active","alias":"rig/gastown.furiosa","agent_name":"rig/gastown.furiosa","session_name":"s-gc-20","created_at":"2026-11-01T10:00:00Z","last_active":"","attached":false,"closed":false}'
CLOSED_ROW='{"id":"gc-10","name":"rig/gastown.furiosa","template":"rig/gastown.polecat","state":"closed","alias":"rig/gastown.furiosa","agent_name":"rig/gastown.furiosa","session_name":"s-gc-10","created_at":"2026-10-31T10:00:00Z","last_active":"","attached":false,"closed":true}'
OLDER_CLOSED_ROW='{"id":"gc-5","name":"rig/gastown.furiosa","template":"rig/gastown.polecat","state":"closed","alias":"rig/gastown.furiosa","agent_name":"rig/gastown.furiosa","session_name":"s-gc-5","created_at":"2026-10-30T10:00:00Z","last_active":"","attached":false,"closed":true}'
roster() {
    local rows="$1"
    printf '{"schema_version":"1","ok":true,"filters":{"state":"all"},"sessions":[%s],"summary":{"total":0,"active":0,"suspended":0,"closed":0}}' "$rows"
}

test_live_owner_beats_older_closed_namesake() {
    set_roster "$(roster "$LIVE_ROW,$CLOSED_ROW")"
    set_session_beads '[]'
    assert_state "rig/gastown.furiosa" active "a live polecat listed before its older closed session"
    assert_state "gc-20" active "the live session's own id"
    assert_state "gc-10" closed "the closed session's own id"
}

test_live_owner_beats_closed_namesake_without_closed_flag() {
    # The city API's rendering before Gas City 1.6 lists closed rows with
    # state "closed" and no closed or agent_name field.
    set_roster '{"sessions":[{"id":"gc-20","name":"rig/gastown.furiosa","alias":"rig/gastown.furiosa","state":"active"},{"id":"gc-10","name":"rig/gastown.furiosa","alias":"rig/gastown.furiosa","state":"closed"}]}'
    set_session_beads '[]'
    assert_state "rig/gastown.furiosa" active "a closed row that carries only state \"closed\""
}

test_closed_session_bead_does_not_displace_live_named_identity() {
    set_roster '{"sessions":[{"id":"gc-30","name":"rig/gastown.alice","alias":"rig/gastown.alice","state":"active","closed":false}]}'
    set_session_beads '[{"id":"gc-30","status":"open","metadata":{"configured_named_identity":"rig/gastown.alice","state":"active"}},{"id":"gc-29","status":"closed","metadata":{"configured_named_identity":"rig/gastown.alice","state":"drained"}}]'
    assert_state "rig/gastown.alice" active "a closed session bead listed after the live one"
}

test_live_owner_beats_closed_namesake_listed_first() {
    set_roster "$(roster "$CLOSED_ROW,$LIVE_ROW")"
    set_session_beads '[]'
    assert_state "rig/gastown.furiosa" active "a closed session listed before the live one"
}

test_identifier_held_only_by_closed_sessions_resolves_closed() {
    # Positive control: an owner that is really gone must still read as
    # closed, or the witness would never recover its work.
    set_roster "$(roster "$CLOSED_ROW,$OLDER_CLOSED_ROW")"
    set_session_beads '[]'
    assert_state "rig/gastown.furiosa" closed "an identifier held only by closed sessions"
}

test_unknown_identifier_resolves_absent() {
    set_roster "$(roster "$LIVE_ROW")"
    set_session_beads '[]'
    assert_state "rig/gastown.nux" absent "an identifier no session holds"
}

test_fail_safe_still_fires_on_an_empty_map() {
    set_roster '{"sessions":[{"state":"active","closed":false}]}'
    set_session_beads '[]'
    : >"$GC_LOG"
    (
        set +eu
        { . "$MAP_BLOCK"; . "$FAILSAFE_BLOCK"; } >"$OUT" 2>&1
    )
    grep -q '^FAIL-SAFE: empty liveness map' "$OUT" ||
        fail "an empty map built while sessions exist did not trip the fail-safe"
    grep -q '^gc mail send mayor/' "$GC_LOG" ||
        fail "the fail-safe did not escalate to the mayor"
}

# Each case runs in its own subshell so one red case does not hide the others.
FAILED=0
run_case() {
    if ( "$1" ); then
        echo "ok   $1"
    else
        echo "FAIL $1" >&2
        FAILED=1
    fi
}

run_case test_live_owner_beats_older_closed_namesake
run_case test_live_owner_beats_closed_namesake_without_closed_flag
run_case test_closed_session_bead_does_not_displace_live_named_identity
run_case test_live_owner_beats_closed_namesake_listed_first
run_case test_identifier_held_only_by_closed_sessions_resolves_closed
run_case test_unknown_identifier_resolves_absent
run_case test_fail_safe_still_fires_on_an_empty_map

[ "$FAILED" -eq 0 ] || exit 1
echo "witness liveness map tests passed"
