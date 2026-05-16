#!/bin/sh
# status-line.sh — tmux status-right helper for Gas City agents.
# Usage: status-line.sh <agent-name>
# Called by tmux every status-interval seconds via #(command).
# Always exits 0 — tmux must never see errors.

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

# Count pending hook nudges with a bounded read-only Beads query. `gc hook`
# can block long enough for tmux to suppress status output.
w=$(json_array_count bd list --include-infra --label gc:nudge --status open --metadata-field "agent=$agent" --json --limit 0)

# Count unread/open message beads with a bounded read-only Beads query.
# `gc mail check` can be too slow for tmux status-right refreshes.
m=$(json_array_count bd list --include-infra --type message --status open --assignee "$agent" --json --limit 0)

# Format: agent | hook-icon N | mail-icon N  (omit segments that are 0)
printf '%s' "$agent"
[ "${w:-0}" -gt 0 ] && printf ' | 🪝 %d' "$w"
[ "${m:-0}" -gt 0 ] && printf ' | 📬 %d' "$m"
exit 0
