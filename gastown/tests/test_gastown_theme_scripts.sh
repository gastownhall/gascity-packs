#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
SCRIPTS="$ROOT/gastown/assets/scripts"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

write_count_stubs() {
    local bin="$1"
    mkdir -p "$bin"

    cat >"$bin/timeout" <<'SH'
#!/usr/bin/env sh
shift
exec "$@"
SH
    chmod +x "$bin/timeout"

    cat >"$bin/gc" <<'SH'
#!/usr/bin/env sh
printf '%s\t%s\n' "$PWD" "$*" >>"$GC_LOG"
case "$PWD $*" in
    *city-a*" hook alpha") printf '[{"id":"work-a"},{"id":"work-b"}]' ;;
    *city-a*" mail check alpha") printf '1 unread message\n' ;;
    *city-b*" hook alpha") printf '[{"id":"work-a"}]' ;;
    *city-b*" mail check alpha") printf '0 unread messages\n' ;;
    *) printf '[]' ;;
esac
SH
    chmod +x "$bin/gc"
}

# Every external command status-line.sh reaches for. The bound probes below run
# with a PATH holding only these, so the helper can be exercised on a host where
# timeout(1) does not exist. A tool missing here does not fail the run cleanly —
# it breaks the cache path and quietly changes what is under test — so resolve
# them all up front and fail loudly instead.
STATUS_LINE_PROBE_TOOLS=(sh sleep mktemp cat rm awk stat jq tr cksum date)

write_bounded_probe_bin() {
    local bin="$1" tool resolved
    mkdir -p "$bin"
    for tool in "${STATUS_LINE_PROBE_TOOLS[@]}"; do
        resolved=$(command -v "$tool" 2>/dev/null) ||
            fail "status-line bound probe needs $tool on PATH"
        ln -sf "$resolved" "$bin/$tool"
    done
}

# Stub gc whose behaviour is chosen by mode: hang stands in for a query wedged
# on a lock, background for one that returns promptly but leaves work running.
write_bounded_probe_gc() {
    local bin="$1" mode="$2" sleeper="$3"

    cat >"$sleeper" <<'SH'
#!/usr/bin/env sh
sleep 60
SH
    chmod +x "$sleeper"

    cat >"$bin/gc" <<SH
#!/usr/bin/env sh
case "$mode" in
    hang)       "$sleeper" ;;
    background) "$sleeper" & ;;
esac
printf '[]\n'
SH
    chmod +x "$bin/gc"
}

# Run status-line.sh detached from this suite's stdio and wait up to cap
# seconds. A wedged run outlives the call, and anything it still holds would
# keep the caller's pipe open — the very failure under test, turned on the
# runner.
run_status_line_watchdog() {
    local run="$1" cap="$2" bin="$3" city="$4" waited=0
    (
        PATH="$bin" GC_STATUSLINE_CACHE_DIR="$run/cache" GC_STATUSLINE_TTL=0 \
            GC_STATUSLINE_BOUND=1 "$SCRIPTS/status-line.sh" alpha "$city" \
            >"$run/out" 2>/dev/null
        : >"$run/done"
    ) >/dev/null 2>&1 &
    while [[ ! -f "$run/done" && "$waited" -lt "$cap" ]]; do
        sleep 1
        waited=$((waited + 1))
    done
    [[ -f "$run/done" ]]
}

# Reap only our own marked probes, by exact pid — never a broad pattern kill.
# pgrep exits non-zero when nothing matches, which is the expected case here, so
# neither helper may let that status escape into the suite's errexit.
reap_marked() {
    local marker="$1" pid
    for pid in $(pgrep -f "$marker" 2>/dev/null || true); do
        kill -KILL "$pid" 2>/dev/null || true
    done
}

marked_survivors() {
    pgrep -f "$1" 2>/dev/null | grep -c . || true
}

test_status_line_counts_with_bounded_gc_commands_and_cache() {
    local tmp city bin cache log output
    tmp=$(mktemp -d)
    city="$tmp/city-a"
    bin="$tmp/bin"
    cache="$tmp/cache"
    log="$tmp/bd.log"
    mkdir -p "$city" "$cache"
    write_count_stubs "$bin"

    if ! output=$(GC_LOG="$log" GC_STATUSLINE_CACHE_DIR="$cache" PATH="$bin:$PATH" "$SCRIPTS/status-line.sh" alpha "$city"); then
        fail "status-line exited non-zero"
    fi

    [[ "$output" == "alpha | 🪝 2 | 📬 1" ]] || fail "unexpected status output: $output"
    grep -F "$city" "$log" >/dev/null || fail "gc was not run from city path"
    grep -F -- $'\thook alpha' "$log" >/dev/null || fail "missing bounded hook query"
    grep -F -- $'\tmail check alpha' "$log" >/dev/null || fail "missing bounded mail check query"

    : >"$log"
    if ! output=$(GC_LOG="$log" GC_STATUSLINE_CACHE_DIR="$cache" PATH="$bin:$PATH" "$SCRIPTS/status-line.sh" alpha "$city"); then
        fail "status-line exited non-zero on cache hit"
    fi

    [[ "$output" == "alpha | 🪝 2 | 📬 1" ]] || fail "unexpected cached status output: $output"
    [[ ! -s "$log" ]] || fail "cache hit still called gc"
}

test_status_line_cache_is_city_scoped() {
    local tmp city_a city_b bin cache log output
    tmp=$(mktemp -d)
    city_a="$tmp/city-a"
    city_b="$tmp/city-b"
    bin="$tmp/bin"
    cache="$tmp/cache"
    log="$tmp/bd.log"
    mkdir -p "$city_a" "$city_b" "$cache"
    write_count_stubs "$bin"

    GC_LOG="$log" GC_STATUSLINE_CACHE_DIR="$cache" PATH="$bin:$PATH" "$SCRIPTS/status-line.sh" alpha "$city_a" >/dev/null

    if ! output=$(GC_LOG="$log" GC_STATUSLINE_CACHE_DIR="$cache" PATH="$bin:$PATH" "$SCRIPTS/status-line.sh" alpha "$city_b"); then
        fail "status-line exited non-zero for second city"
    fi

    [[ "$output" == "alpha | 🪝 1" ]] || fail "cache was not city scoped, got: $output"
    grep -F "$city_b" "$log" >/dev/null || fail "second city did not run its own query"
}

test_status_line_falls_back_to_agent_only_on_query_failure() {
    local tmp bin cache output
    tmp=$(mktemp -d)
    bin="$tmp/bin"
    cache="$tmp/cache"
    mkdir -p "$bin" "$cache"

    cat >"$bin/gc" <<'SH'
#!/usr/bin/env sh
exit 2
SH
    chmod +x "$bin/gc"

    if ! output=$(GC_STATUSLINE_CACHE_DIR="$cache" PATH="$bin:$PATH" "$SCRIPTS/status-line.sh" alpha "$tmp"); then
        fail "status-line exited non-zero on query failure"
    fi

    [[ "$output" == "alpha" ]] || fail "expected fallback status output, got: $output"
}

test_status_line_counts_ready_work_not_queued_nudges() {
    local tmp city bin cache output
    tmp=$(mktemp -d)
    city="$tmp/city"
    bin="$tmp/bin"
    cache="$tmp/cache"
    mkdir -p "$city" "$bin" "$cache"

    cat >"$bin/timeout" <<'SH'
#!/usr/bin/env sh
shift
exec "$@"
SH
    chmod +x "$bin/timeout"

    cat >"$bin/gc" <<'SH'
#!/usr/bin/env sh
case "$*" in
    "hook alpha") printf '[{"id":"ready-work"}]' ;;
    "mail check alpha") printf '0 unread messages\n' ;;
    "hook beta") printf '[]' ;;
    "mail check beta") printf '0 unread messages\n' ;;
esac
SH
    chmod +x "$bin/gc"

    cat >"$bin/bd" <<'SH'
#!/usr/bin/env sh
printf '[]\n'
SH
    chmod +x "$bin/bd"

    if ! output=$(GC_STATUSLINE_CACHE_DIR="$cache" PATH="$bin:$PATH" "$SCRIPTS/status-line.sh" alpha "$city"); then
        fail "status-line exited non-zero for ready-work semantics"
    fi

    [[ "$output" == "alpha | 🪝 1" ]] || fail "expected ready work count from gc hook, got: $output"

    if ! output=$(GC_STATUSLINE_CACHE_DIR="$cache" PATH="$bin:$PATH" "$SCRIPTS/status-line.sh" beta "$city"); then
        fail "status-line exited non-zero for idle ready-work semantics"
    fi

    [[ "$output" == "beta" ]] || fail "expected empty hook array to be omitted, got: $output"
}

test_status_line_uses_unread_mail_check_semantics() {
    local tmp city bin cache output
    tmp=$(mktemp -d)
    city="$tmp/city"
    bin="$tmp/bin"
    cache="$tmp/cache"
    mkdir -p "$city" "$bin" "$cache"

    cat >"$bin/timeout" <<'SH'
#!/usr/bin/env sh
shift
exec "$@"
SH
    chmod +x "$bin/timeout"

    cat >"$bin/gc" <<'SH'
#!/usr/bin/env sh
case "$*" in
    "hook alpha") printf '[]' ;;
    "mail check alpha") printf '0 unread messages\n' ;;
esac
SH
    chmod +x "$bin/gc"

    cat >"$bin/bd" <<'SH'
#!/usr/bin/env sh
printf '[{"labels":["read"]}]\n'
SH
    chmod +x "$bin/bd"

    if ! output=$(GC_STATUSLINE_CACHE_DIR="$cache" PATH="$bin:$PATH" "$SCRIPTS/status-line.sh" alpha "$city"); then
        fail "status-line exited non-zero for unread mail semantics"
    fi

    [[ "$output" == "alpha" ]] || fail "expected read mail to be omitted, got: $output"
}

test_status_line_bounds_a_hanging_query_without_timeout_binary() {
    local tmp bin city run marker
    tmp=$(mktemp -d)
    bin="$tmp/bin"
    city="$tmp/city"
    run="$tmp/run"
    marker="statusline_bound_hang_$$"
    mkdir -p "$city" "$run"

    write_bounded_probe_bin "$bin"
    # Positive control: the probe bin is the whole PATH for the run below, so
    # timeout(1) is reachable only if it was linked in. Assert it was not — if
    # it ever is, this case silently degrades into "timeout did the bounding"
    # and stops covering the platforms that ship no coreutils.
    [[ ! -e "$bin/timeout" ]] ||
        fail "probe PATH still resolves timeout(1); the no-timeout case would be vacuous"
    write_bounded_probe_gc "$bin" hang "$tmp/$marker.sh"

    if ! run_status_line_watchdog "$run" 20 "$bin" "$city"; then
        reap_marked "$marker"
        fail "hanging query was never bounded where timeout(1) is absent"
    fi
    reap_marked "$marker"
}

test_status_line_reaps_work_the_query_leaves_behind() {
    local tmp bin city run marker survivors wedged=0
    tmp=$(mktemp -d)
    bin="$tmp/bin"
    city="$tmp/city"
    run="$tmp/run"
    marker="statusline_bound_bg_$$"
    mkdir -p "$city" "$run"

    write_bounded_probe_bin "$bin"
    write_bounded_probe_gc "$bin" background "$tmp/$marker.sh"

    # A bound on the direct child alone leaves the backgrounded grandchild
    # running, and that grandchild inherits stdout — so the refresh both leaks
    # a process and blocks the caller reading through the pipe.
    run_status_line_watchdog "$run" 20 "$bin" "$city" || wedged=1
    survivors=$(marked_survivors "$marker")
    reap_marked "$marker"

    [[ "$wedged" -eq 0 ]] ||
        fail "refresh never completed — caller wedged by a grandchild holding stdout"
    [[ "$survivors" -eq 0 ]] ||
        fail "backgrounded work survived the bound ($survivors still running)"
}

test_tmux_theme_passes_city_path_to_status_helper() {
    local tmp bin log city
    tmp=$(mktemp -d)
    bin="$tmp/bin"
    log="$tmp/tmux.log"
    city="$tmp/city with spaces"
    mkdir -p "$bin" "$city"

    cat >"$bin/tmux" <<'SH'
#!/usr/bin/env sh
printf '%s\n' "$*" >>"$TMUX_LOG"
SH
    chmod +x "$bin/tmux"

    GC_CITY="$city" TMUX_LOG="$log" PATH="$bin:$PATH" "$SCRIPTS/tmux-theme.sh" session-alpha alpha "$ROOT/gastown"

    grep -F -- "status-right #('$ROOT/gastown/assets/scripts/status-line.sh' 'alpha' '$city') %H:%M" "$log" >/dev/null ||
        fail "tmux-theme did not quote and pass city path to status-line"
}

test_status_line_counts_with_bounded_gc_commands_and_cache
test_status_line_cache_is_city_scoped
test_status_line_falls_back_to_agent_only_on_query_failure
test_status_line_counts_ready_work_not_queued_nudges
test_status_line_uses_unread_mail_check_semantics
test_status_line_bounds_a_hanging_query_without_timeout_binary
test_status_line_reaps_work_the_query_leaves_behind
test_tmux_theme_passes_city_path_to_status_helper

echo "gastown theme script tests passed"
