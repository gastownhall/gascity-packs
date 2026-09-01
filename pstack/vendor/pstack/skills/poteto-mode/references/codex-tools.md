# Codex tool mapping for pstack

Shared skill bodies in this tree use **Grok Build** call-site names after the grokbuild adapter (`task`, `ask_user_question`, `todo_write`). See `skills/poteto-mode/SKILL.md` Subagents. On Codex those names resolve to Codex primitives. On Claude Code they resolve to `Agent` / structured questions. Model routing is in [`provider-dispatch.md`](provider-dispatch.md).

## Tool actions

| Shared skill language (Grok-facing) | Codex | Claude Code |
| --- | --- | --- |
| Read / edit / shell / search | `shell`, `apply_patch`, `rg` | Claude Read / Edit / Bash |
| Fetch a URL | `shell` with `curl` | Claude WebFetch / Bash |
| Invoke a skill | Skills load natively | Skills load natively |
| Spawn (`task` / `spawn_subagent`) | `spawn_agent` | `Agent` |
| N parallel children | N `spawn_agent` in one turn | N `Agent` in one turn |
| Wait / join | `wait_agent` | wait on Agent handles |
| Todos (`todo_write`) | `update_plan` | Claude todolist |
| Ask a fixed-choice question (`ask_user_question`) | Ask in plain text | `AskUserQuestion` |

Subagent dispatch on Codex needs `multi_agent` in `~/.codex/config.toml`:

```toml
[features]
multi_agent = true
```

Without it, the native Codex lane is a named dropout. Never collapse a panel into a sequential single-model pass.

## Subagent policy

poteto-mode Subagents defaults are Grok `task` fields (`subagent_type`, `run_in_background: true`). Translate:

- Codex has no `poteto-agent` type. Dispatch `spawn_agent` told to read `poteto-mode` first.
- `spawn_agent` is already concurrent; there is no `run_in_background` flag.
- No `comment-sicko` type: `spawn_agent` told to read `agents/comment-sicko.md`.
- Writers isolate with worktrees (`isolation: worktree` on Grok `task`; Codex isolated worktree).
- Pass file pointers, not inlined dumps. Parent owns every spawn (depth 1).

## Models

`/setup-pstack` writes **detected** host slugs. On a Codex parent, native `codex:*` uses `spawn_agent`. Other providers are optional outbound runners, not this in-process host. Do not send Cursor marketplace panel slugs as live models.

## Overnight / babysit / shipping

Cursor same-run `/loop` is **not** live.

| Host | Overnight |
| --- | --- |
| Grok Build | Persist trail. Event: `monitor`. Heartbeat: `/loop` → `scheduler_create` (new turn). |
| Claude Code | Built-in `loop` skill. |
| Codex | Re-run the step on a cadence or a Codex scheduled task. |

## Vendored scripts

`skills/poteto-mode/scripts/worktree-audit.sh` is bash. Invoke through `shell`. Transcript paths: Grok `~/.grok/sessions/`; Claude `~/.claude/projects/`; Codex session storage. Not `~/.cursor/projects/`. This pack omits `watch-pr` and `orch`.

## Instructions file

Codex: `AGENTS.md`. Claude Code: `CLAUDE.md`. Grok Build: `AGENTS.md` plus `HARNESS.md`.
