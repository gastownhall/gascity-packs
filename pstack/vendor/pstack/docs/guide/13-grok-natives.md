# Grok Build natives vs pstack

Inventory is grok **1.0.13** (`grok --version`), user-guide under `~/.grok/docs/user-guide/`, and grok-build `PluginManifest` / slash docs. The live pstack map stays [`HARNESS.md`](../../HARNESS.md). This page lists natives pstack does **not** wrap, and a plan: adopt, skip, or gap.

## Already mapped

Spawn, join, cancel, roles `pstack:<key>`, isolation, resume, depth 1, todos, `ask_user_question`, `/loop` → `scheduler_create`, `monitor`, skill order, Benny as plugin skills, no plugin `hooks` or `commands/`. See HARNESS.

## CLI (`grok --help`)

| Native | Plan |
|---|---|
| `grok --worktree` / `grok worktree` | **Skip for now.** Playbooks already set `isolation: worktree` on spawn. CLI worktree is for starting the **session**, not a child. |
| `grok -p` / `--single` / `grok agent` | **Gap fill for Benny auto-start only.** Document as an external webhook into `grok -p "/benny-triage <url>"`. Not a playbook rewrite. |
| `--json-schema` | **Skip.** Workflow `output_schema` already covers structured child output. |
| `--no-subagents` `--no-plan` | **Skip.** Operator session flags. Playbooks assume spawn works. |
| `--permission-mode plan` | **Skip.** pstack uses `/architect` and `/interrogate`, not agent `permissionMode: plan` (forbidden in plugin agents). |
| `--sandbox workspace` | **Daily driver for pstack.** Writes CWD + `~/.grok/` except pinned `config.toml` / `hooks/` under bwrap. |
| `--sandbox homelab` | **Custom.** Extends workspace. Extra `~/.npm` and cache writes. Same config.toml EROFS. |
| `--sandbox off` | **Host-shell only** for `plugin enable` / `config.toml`. Not the all-day TUI. |
| `grok clone` | **Skip.** Grove/FUSE. Not a pstack primitive. |
| `grok mcp add` | **Skip.** User MCP config, not plugin `.mcp.json`. |
| `grok inspect --json` | **Keep.** First-session proof of enable. |
| `grok plugin validate` | **Keep.** Harness tests run it. `grok plugin tag` still waits for a release. |

## Slash and tools (04-slash-commands, 19-plan-mode)

| Native | Plan |
|---|---|
| `/plan` `enter_plan_mode` | **Skip.** Skill order already lists builtin `/plan` as column 3 after pstack architect. Do not clone a `/plan` command. |
| `/goal` | **Skip.** `/figure-it-out` owns rigor playbooks. Autopilot playbooks must not arm `/goal`. Goal mode is a different driver. |
| `/workflow` `/deep-research` | **Skip as plugin.** Target-repo Rhai only. ADR 0005. `agent_type: pstack:<role>` is the join. |
| `/memory` `/flush` `/dream` `/remember` | **Skip.** Off by default. pstack overnight uses `show-me-your-work`. |
| `/fork` `/rewind` `/compact` | **Skip.** Session UX, not playbook steps. |
| `/imagine` | **Skip** unless a domain pack needs images. |
| `/hooks` plugin `hooks/` | **Skip global.** ADR 0003. Benny fail-closed stays opt-in. |
| `/mcps` plugin `.mcp.json` | **Skip.** Do not bundle Slack MCP in the plugin. |
| LSP `.lsp.json` | **Skip.** |

## Applied from this inventory

1. `tests/test_verify_harness.py` runs `grok plugin validate` on the tree.
2. Overnight guide names `grok --worktree` as a session start. Spawn isolation stays `isolation: worktree`.
3. Benny README: optional `grok -p '/benny-triage <permalink>'` webhook. Not Slack auto-start.
4. `grok plugin tag` still wait-for-release.

Do not add `commands/`. Do not add plugin `hooks`. Do not wrap `/goal` or `/plan` as pstack slash clones.

Next: [Port pstack](./12-porting.md) to put these rows on another host's checklist.
