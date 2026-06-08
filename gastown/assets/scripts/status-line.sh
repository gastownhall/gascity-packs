#!/bin/sh
# status-line.sh — tmux status-right helper for Gas Town agents.
# Usage: status-line.sh <agent-name> [city-path]
# Called by tmux every status-interval seconds via #(command).
# Always exits 0 — tmux must never see errors.
#
# Counts are cached with a short TTL so tmux's frequent refresh does not query
# Beads on every render across every agent. TTL override:
# GC_STATUSLINE_TTL (seconds). Cache directory override:
# GC_STATUSLINE_CACHE_DIR.

agent="$1"
city="${2:-${GC_CITY:-${GT_ROOT:-${GC_DIR:-}}}}"
[ -z "$agent" ] && exit 0

if [ -n "$city" ] && [ -d "$city" ]; then
    cd "$city" 2>/dev/null || true
fi

run_bounded() {
    if command -v timeout >/dev/null 2>&1; then
        timeout 2s "$@"
    else
        "$@"
    fi
}

json_array_count() {
    if ! command -v jq >/dev/null 2>&1; then
        printf '0'
        return 0
    fi

    n=$(run_bounded "$@" 2>/dev/null | jq 'length' 2>/dev/null || true)
    case "$n" in
        ''|*[!0-9]*) printf '0' ;;
        *) printf '%s' "$n" ;;
    esac
}

cache_mtime() {
    stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || printf '0'
}

is_number() {
    case "$1" in
        ''|*[!0-9]*) return 1 ;;
        *) return 0 ;;
    esac
}

cache_ttl="${GC_STATUSLINE_TTL:-30}"
is_number "$cache_ttl" || cache_ttl=30
cache_dir="${GC_STATUSLINE_CACHE_DIR:-${TMPDIR:-/tmp}}"
cache_city=$(pwd -P 2>/dev/null || pwd)
safe_agent=$(printf '%s' "$agent" | tr -c 'A-Za-z0-9._-' '_')
cache_key=$(printf '%s\n%s\n' "$cache_city" "$agent" | cksum | awk '{print $1}')
cache="$cache_dir/gc-statusline-${safe_agent}-${cache_key}.cache"

now=$(date +%s 2>/dev/null || printf '0')
mtime=$(cache_mtime "$cache")
if is_number "$now" && is_number "$mtime" && [ "$mtime" -gt 0 ] && [ "$((now - mtime))" -lt "$cache_ttl" ]; then
    read -r w m < "$cache" 2>/dev/null || true
    is_number "${w:-}" || w=0
    is_number "${m:-}" || m=0
else
    # Count pending hook nudges with a bounded read-only Beads query. `gc hook`
    # can block long enough for tmux to suppress status output.
    w=$(json_array_count bd list --include-infra --label gc:nudge --status open --metadata-field "agent=$agent" --json --limit 0)

    # Count unread/open message beads with a bounded read-only Beads query.
    # `gc mail check` can be too slow for tmux status-right refreshes.
    m=$(json_array_count bd list --include-infra --type message --status open --assignee "$agent" --json --limit 0)

    mkdir -p "$cache_dir" 2>/dev/null || true
    printf '%s %s\n' "${w:-0}" "${m:-0}" > "$cache" 2>/dev/null || true
fi

# Format: agent | hook-icon N | mail-icon N  (omit segments that are 0)
printf '%s' "$agent"
[ "${w:-0}" -gt 0 ] && printf ' | 🪝 %d' "$w"
[ "${m:-0}" -gt 0 ] && printf ' | 📬 %d' "$m"
exit 0
