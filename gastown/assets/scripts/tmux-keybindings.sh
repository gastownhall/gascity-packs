#!/bin/sh
# tmux-keybindings.sh — Gas Town navigation keybindings (n/p/g/a + mail click)
# Usage: tmux-keybindings.sh <config-dir>
CONFIGDIR="$1"

# Socket-aware tmux command (uses GC_TMUX_SOCKET when set).
gcmux() { tmux ${GC_TMUX_SOCKET:+-L "$GC_TMUX_SOCKET"} "$@"; }

# ── Navigation bindings (prefix table) ────────────────────────────────
"$CONFIGDIR"/assets/scripts/bind-key.sh n "run-shell '$CONFIGDIR/assets/scripts/cycle.sh next #{session_name} #{client_tty}'"
"$CONFIGDIR"/assets/scripts/bind-key.sh p "run-shell '$CONFIGDIR/assets/scripts/cycle.sh prev #{session_name} #{client_tty}'"
"$CONFIGDIR"/assets/scripts/bind-key.sh g "run-shell '$CONFIGDIR/assets/scripts/agent-menu.sh #{client_tty}'"

# ── Mail click binding (root table: left-click on status-right) ───────
# Shows unread mail preview in a popup when clicking the status-right area.
# Per-city socket isolation makes every session on this socket a GC
# session, so we install the popup directly without an if-shell guard.
mail_popup="display-popup -E -w 60 -h 15 'gc mail peek || echo No unread mail'"
existing=$(gcmux list-keys -T root MouseDown1StatusRight 2>/dev/null || true)
if ! printf '%s' "$existing" | grep -qF "$mail_popup"; then
    gcmux bind-key -T root MouseDown1StatusRight "$mail_popup"
fi

# ── Mouse-wheel scrollback (root table) ───────────────────────────────
# WheelUp drives tmux copy-mode scrollback when a plain shell (or any pane
# not using the terminal alternate screen) is focused. When the focused pane
# IS in alternate-screen mode — Claude Code's TUI, a pager, or any other
# full-screen app — the wheel is passed through to the application so its own
# history/scroll works as expected. Rationale: the tmux scrollback buffer
# contains no content from alternate-screen apps (their output never lands
# there), so entering copy-mode while Claude Code is focused gives an empty
# scrollback, silently discarding the intended scroll.
#   #{alternate_on}   — pane is currently in the terminal alternate screen
#   #{pane_in_mode}   — already in tmux copy-mode (wheel continues scrolling)
#   #{mouse_any_flag} — app has requested mouse tracking (belt-and-suspenders)
# WheelDown always passes through; -e in copy-mode exits at the bottom.
# Shift+wheel still does native terminal selection.
gcmux bind-key -T root WheelUpPane   if-shell -F -t= "#{||:#{alternate_on},#{pane_in_mode},#{mouse_any_flag}}" "send-keys -M" "copy-mode -e"
gcmux bind-key -T root WheelDownPane send-keys -M
