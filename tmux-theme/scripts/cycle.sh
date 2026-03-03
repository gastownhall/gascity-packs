#!/bin/sh
# cycle.sh — cycle between Gas City agent sessions.
# Usage: cycle.sh next|prev <current-session> <client-tty>
# Called via tmux run-shell from a keybinding.
#
# Generic version: cycles through all gc-* sessions alphabetically.
# Pack-specific overrides can replace this with role-aware grouping
# (e.g., gastown's cycle.sh groups by town/rig/pool).

direction="$1"
current="$2"
client="$3"

[ -z "$direction" ] || [ -z "$current" ] || [ -z "$client" ] && exit 0

# Get target session: find current in sorted gc-* list, pick next/prev.
target=$(tmux list-sessions -F '#{session_name}' 2>/dev/null \
    | grep '^gc-' \
    | sort \
    | awk -v cur="$current" -v dir="$direction" '
        { a[NR] = $0; if ($0 == cur) idx = NR }
        END {
            if (NR <= 1 || idx == 0) exit
            if (dir == "next") t = (idx % NR) + 1
            else t = ((idx - 2 + NR) % NR) + 1
            print a[t]
        }')

[ -z "$target" ] && exit 0
tmux switch-client -c "$client" -t "$target"
