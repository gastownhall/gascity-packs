#!/bin/sh
# tmux-keybindings.sh — Gas City navigation keybindings (n/p/g).
# Usage: tmux-keybindings.sh <config-dir>
CONFIGDIR="$1"
"$CONFIGDIR"/scripts/bind-key.sh n "run-shell '$CONFIGDIR/scripts/cycle.sh next #{session_name} #{client_tty}'"
"$CONFIGDIR"/scripts/bind-key.sh p "run-shell '$CONFIGDIR/scripts/cycle.sh prev #{session_name} #{client_tty}'"
"$CONFIGDIR"/scripts/bind-key.sh g "run-shell '$CONFIGDIR/scripts/agent-menu.sh #{client_tty}'"
