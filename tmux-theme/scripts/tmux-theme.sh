#!/bin/sh
# tmux-theme.sh — Gas City status bar theme.
# Usage: tmux-theme.sh <session> <agent> <config-dir>
SESSION="$1" AGENT="$2" CONFIGDIR="$3"

# Socket-aware tmux command (uses GC_TMUX_SOCKET when set).
gcmux() { tmux ${GC_TMUX_SOCKET:+-L "$GC_TMUX_SOCKET"} "$@"; }

gcmux set-option -t "$SESSION" status-right-length 80
gcmux set-option -t "$SESSION" status-interval 5
gcmux set-option -t "$SESSION" status-right "#($CONFIGDIR/scripts/status-line.sh $AGENT) %H:%M"
