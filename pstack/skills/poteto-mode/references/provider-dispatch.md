# Provider dispatch

Shared pstack blocks recompose on **Grok Build**, **Codex**, and **Claude Code**. The parent owns every route. Children never detect the host or spawn.

## Descriptors

```text
<provider>:<model>@<effort>
```

`inherit-parent` and `auto` omit host `model` so the child uses the parent session.

## Stock routes (no Cursor panel slugs as live fallbacks)

Do not send Cursor marketplace panel slugs as live spawn models unless `/setup-pstack` confirmed they exist on **this** host. Stock Grok Build uses `grok-4.6` and `grok-4.5` only.

| Role | Grok Build | Codex | Claude Code |
| --- | --- | --- | --- |
| Judgment / prose | `grok-4.6` | detected Codex slug | detected Claude slug |
| Mechanical / fast | `grok-4.5` | detected Codex slug | detected Claude slug |
| Panel seats | unique detected slugs only; never four copies of one slug | same | same |

Effort on Grok Build is role overlay (`~/.grok/roles/pstack:<key>.toml`) or agent frontmatter. Do not send `reasoning_effort` on Grok `task`. Codex may pass `reasoning_effort` on `spawn_agent` when that host supports it.

## Parent spawn

| Parent | Spawn |
| --- | --- |
| Grok Build | `task` (TUI alias `spawn_subagent`). Depth 1. `isolation: worktree` for writers. |
| Claude Code | `Agent`. Depth 1. Native Claude models stay in-process. |
| Codex | `spawn_agent` / `wait_agent` with `multi_agent = true`. Depth 1. |

## Mapping files

- Grok Build: `HARNESS.md` at plugin root
- Codex: this file plus `codex-tools.md`
- Claude Code: `.claude-plugin/plugin.json` plus Claude `Agent`

Optional external CLI runner under `skills/poteto-mode/scripts/runner/` is for **outbound** other-provider lanes, not for Grok Build as the in-process host.
