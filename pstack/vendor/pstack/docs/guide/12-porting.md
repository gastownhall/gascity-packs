# Port pstack to another agent harness

Official pstack (poteto, Cursor plugin pin `6fecddba`) is a philosophy plus a file layout. This Grok port is a **reference implementation** of that layout. Use this page to port the core onto **any** new agent whose tools you can name.

The host map is the only required new file. Fill the checklist from that agent's docs or source. Write `gap` when the host has no equivalent. Playbooks then call the names you wrote, not Cursor spawn fields.

## Philosophy (keep this)

From the official README and `docs/guide/08-principles.md`:

- **Less code, higher quality.** Throughput without quality is not the goal. Opposite of maximizing loc.
- **Go deep, then parallelize.** Trust each agent because it applies the same principles. Then fan out.
- **One router.** `/poteto-mode` matches a playbook and calls situational skills. The operator gives a goal and a checkable outcome in their own words.
- **Steer with principle names.** 21 principles as leaf skills. You do not invoke them. One phrase redirects. The agent must name the decision the principle changed.
- **Prove on the real artifact.** Compiling is not done.
- **Never block on reversible work.** Pause on irreversible writes.
- **Encode lessons in structure.** The second time you write an instruction, turn it into a check or script. **Laziness Protocol** is the default sizing rule: smallest change, prefer deletion.

A port that copies files and keeps the previous host's spawn fields is not a port.

## Three layers

| Layer | What | Port how |
|---|---|---|
| Core | 21 `principle-*` skills, 22 playbook **intents**, router skill shape, unslop, no-comments, tdd, how, why | Copy. Keep names. |
| Host map | One file the router reads first | Fill the checklist below. Grok reference: [`HARNESS.md`](../../HARNESS.md). Codex: `skills/poteto-mode/references/codex-tools.md`. |
| Domain packs | Benny, TypeScript practices, visual-parity, Graphite shipping | Keep only if the domain matches. |

## Capability checklist

Inventory the new agent from its **docs and source**, not from memory. For each pstack need, write the live primitive or write `gap`.

| pstack need | What to find on the new host | Grok reference (this tree) |
|---|---|---|
| Slash / skill load | How SKILL.md becomes `/name`. Frontmatter the host actually parses. | Plugin `skills/` |
| Install / enable / trust | Manifest path, enable list vs inspect "enabled". Sandbox write limits. | `plugin.json`, `[plugins].enabled`, EROFS on `config.toml` |
| Spawn a child | Tool id and fields. Default type. | `spawn_subagent` (wire `task`) |
| Background | Field name and default. | `background` (TUI default false) |
| Join / wait | Block vs poll. Id field. | `get_command_or_subagent_output` |
| Cancel | Kill primitive. | `kill_command_or_subagent` |
| Role types | How plugin agents are named. Prefix? Overlay path. | `pstack:<role-key>`, `~/.grok/roles/pstack:<key>.toml` |
| Model per spawn | Optional slug. Inherit parent? | `model`, omit to inherit |
| Effort | On spawn vs agent frontmatter vs overlay. Live enum. | Frontmatter `effort` or overlay. No spawn `reasoning_effort` field here. |
| Read-only child | Real field or a role with no edit tools. Ignored JSON is a `gap`. | `pstack:how-explorer` (not a spawn capability field) |
| Isolation | Worktree vs cwd. | `isolation: none \| worktree` |
| Resume | Same type, prior id. | `resume_from` |
| Nested spawn | Max depth. If 1, parent fans out. | `MAX_SUBAGENT_DEPTH` 1 |
| Todos | Merge semantics and statuses. | `todo_write` |
| Ask the human | Fixed-choice only. Product or preference. | `ask_user_question` |
| Overnight loop | Same-run vs persist-then-wake. Min interval. | `/loop` → `scheduler_create` (new turn, min 60s) |
| Watch | Log or process watch without polling. | `monitor` |
| Skill order | Plugin vs user vs builtin. | pstack, then user, then bundled |
| Workflows | Plugin-shipped or project/user dirs only. | Not a plugin field. Target `.grok/workflows/` |
| Hooks | Plugin-global vs opt-in. | This plugin has no `hooks` key |

Write `gap` for a missing row. Do not invent a field the host ignores. A `gap` means playbooks skip that step with `skip: host has no overnight primitive` (or the real reason).

## Follow these steps

1. Fill the capability checklist from the new agent's user guide and, if you have it, the loader source (manifest struct, spawn input type).
2. Copy `skills/principle-*` and `skills/poteto-mode/` (playbooks + router).
3. Write `<host-map>.md` as a table like [`HARNESS.md`](../../HARNESS.md) **Mapping**. Point the router's first todo at that file (see `skills/poteto-mode/SKILL.md` Non-negotiables).
4. Register skills and role agents in the host's plugin or skill dirs. Do not add `commands/` clones of slash skills unless the host has no skill `/name`.
5. Rewrite playbook call sites to the map's names. Parent owns fan-out when nested spawn is a `gap` or depth is 1.
6. Add a scanner that forbids leftover identifiers from the **previous** host in playbooks (this repo: `scripts/verify-harness.py`). Tests must fail on a leftover name.
7. Domain packs last. Skip canvases the host lacks. Skip Benny until Slack and fail-closed are remapped. Do not ship a global merge-deny hook.

This repo did those steps for Grok Build. `UPSTREAM` names the Cursor pin. `scripts/sync-from-upstream.py` is print-only. `adapt-harness.py` rewrites Cursor call sites.

## What not to copy as "core"

- Previous host spawn field names and panel slugs.
- Plugin-global merge-deny hooks.
- Workflow clones of playbooks (ADR 0005). If the host has workflows, they live in a **target** repo.
- A 63-plugin marketplace tree. pstack is one plugin.

Next: [Grok Build workflows](./11-grok-workflows.md) if the host is Grok. Official principles: [Steer with principle names](./08-principles.md).
