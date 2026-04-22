# tmux Theme Pack

tmux status-bar theming and navigation keybindings for Gas City agent sessions.

This pack installs a `session_live` hook that runs on every agent session
start. The hook applies a colored status bar, live hook/mail indicators, and
a small set of navigation keybindings scoped to GC sessions on the socket.

## What It Provides

- **Status bar theme** — per-agent background/foreground colors from a
  10-color palette, chosen by consistent hash of the agent name so the same
  agent always gets the same color. Matches the Go `DefaultPalette` in
  `internal/session/tmux/theme.go`.
- **Live status-right** — refreshes every 5 seconds via `gc hook` and
  `gc mail check`; shows pending hooks and unread mail counts per agent.
- **Prefix keybindings** — `n` / `p` cycle through related agent sessions
  (rig ops, rig crew, town group, dog pool), `g` opens a popup menu of all
  agent sessions on the socket.
- **Mail click binding** — left-click the status-right region to pop up
  `gc mail peek` for the current session. Preserves any pre-existing root
  `MouseDown1StatusRight` binding as the non-GC fallback.
- **Mouse and clipboard** — turned on for every agent session.

All tmux commands are socket-aware; `GC_TMUX_SOCKET`, when set, is forwarded
through a `gcmux` wrapper so per-city socket isolation keeps working.

## Import It

```toml
[imports.tmux-theme]
source = "../packs/tmux-theme"
```

No prerequisites beyond `tmux` itself, which Gas City already requires.

## Keybindings

All bindings live on the tmux prefix table and fire only inside GC sessions
(guarded by the `GC_AGENT` environment variable); non-GC sessions keep their
original bindings.

| Binding | Action |
|---------|--------|
| `prefix n` | Next session in the current agent group |
| `prefix p` | Previous session in the current agent group |
| `prefix g` | Popup menu of all agent sessions on this socket |
| Click status-right | Popup preview of unread mail for the current session |

Grouping rules for `n`/`p`:

- Rig ops: `{rig}--witness` ↔ `{rig}--refinery` ↔ `{rig}--polecat-*`
- Rig crew: other `{rig}--{name}` members in the same rig
- Town group: `mayor` ↔ `deacon`
- Dog pool: `dog-1` ↔ `dog-2` ↔ `dog-3`
- Fallback: all sessions on the socket
