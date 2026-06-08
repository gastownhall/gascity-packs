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

    cat >"$bin/jq" <<'SH'
#!/usr/bin/env sh
input=$(cat)
case "$input" in
    "[{},{}]") printf '2\n' ;;
    "[{}]") printf '1\n' ;;
    "[]") printf '0\n' ;;
    *) printf '0\n' ;;
esac
SH
    chmod +x "$bin/jq"

    cat >"$bin/bd" <<'SH'
#!/usr/bin/env sh
printf '%s\t%s\n' "$PWD" "$*" >>"$BD_LOG"
case "$PWD $*" in
    *city-a*" --label gc:nudge "*) printf '[{},{}]\n' ;;
    *city-a*" --type message "*) printf '[{}]\n' ;;
    *city-b*" --label gc:nudge "*) printf '[{}]\n' ;;
    *city-b*" --type message "*) printf '[]\n' ;;
    *) printf '[]\n' ;;
esac
SH
    chmod +x "$bin/bd"
}

test_status_line_counts_with_bounded_bd_queries_and_cache() {
    local tmp city bin cache log output
    tmp=$(mktemp -d)
    city="$tmp/city-a"
    bin="$tmp/bin"
    cache="$tmp/cache"
    log="$tmp/bd.log"
    mkdir -p "$city" "$cache"
    write_count_stubs "$bin"

    if ! output=$(BD_LOG="$log" GC_STATUSLINE_CACHE_DIR="$cache" PATH="$bin:$PATH" "$SCRIPTS/status-line.sh" alpha "$city"); then
        fail "status-line exited non-zero"
    fi

    [[ "$output" == "alpha | 🪝 2 | 📬 1" ]] || fail "unexpected status output: $output"
    grep -F "$city" "$log" >/dev/null || fail "bd was not run from city path"
    grep -F -- "list --include-infra --label gc:nudge --status open --metadata-field agent=alpha --json --limit 0" "$log" >/dev/null ||
        fail "missing bounded nudge query"
    grep -F -- "list --include-infra --type message --status open --assignee alpha --json --limit 0" "$log" >/dev/null ||
        fail "missing bounded message query"

    : >"$log"
    if ! output=$(BD_LOG="$log" GC_STATUSLINE_CACHE_DIR="$cache" PATH="$bin:$PATH" "$SCRIPTS/status-line.sh" alpha "$city"); then
        fail "status-line exited non-zero on cache hit"
    fi

    [[ "$output" == "alpha | 🪝 2 | 📬 1" ]] || fail "unexpected cached status output: $output"
    [[ ! -s "$log" ]] || fail "cache hit still called bd"
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

    BD_LOG="$log" GC_STATUSLINE_CACHE_DIR="$cache" PATH="$bin:$PATH" "$SCRIPTS/status-line.sh" alpha "$city_a" >/dev/null

    if ! output=$(BD_LOG="$log" GC_STATUSLINE_CACHE_DIR="$cache" PATH="$bin:$PATH" "$SCRIPTS/status-line.sh" alpha "$city_b"); then
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

    cat >"$bin/bd" <<'SH'
#!/usr/bin/env sh
exit 2
SH
    chmod +x "$bin/bd"
    cat >"$bin/jq" <<'SH'
#!/usr/bin/env sh
exit 2
SH
    chmod +x "$bin/jq"

    if ! output=$(GC_STATUSLINE_CACHE_DIR="$cache" PATH="$bin:$PATH" "$SCRIPTS/status-line.sh" alpha "$tmp"); then
        fail "status-line exited non-zero on query failure"
    fi

    [[ "$output" == "alpha" ]] || fail "expected fallback status output, got: $output"
}

test_tmux_theme_passes_city_path_to_status_helper() {
    local tmp bin log city
    tmp=$(mktemp -d)
    bin="$tmp/bin"
    log="$tmp/tmux.log"
    city="$tmp/city"
    mkdir -p "$bin" "$city"

    cat >"$bin/tmux" <<'SH'
#!/usr/bin/env sh
printf '%s\n' "$*" >>"$TMUX_LOG"
SH
    chmod +x "$bin/tmux"

    GC_CITY="$city" TMUX_LOG="$log" PATH="$bin:$PATH" "$SCRIPTS/tmux-theme.sh" session-alpha alpha "$ROOT/gastown"

    grep -F -- "status-right #($ROOT/gastown/assets/scripts/status-line.sh alpha $city) %H:%M" "$log" >/dev/null ||
        fail "tmux-theme did not pass city path to status-line"
}

test_status_line_counts_with_bounded_bd_queries_and_cache
test_status_line_cache_is_city_scoped
test_status_line_falls_back_to_agent_only_on_query_failure
test_tmux_theme_passes_city_path_to_status_helper

echo "gastown theme script tests passed"
