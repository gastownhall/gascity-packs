# Resolve reasoning effort

Every pstack skill that spawns `task` uses this rule together with [`resolve-model.md`](resolve-model.md). Read it once, then apply it at the spawn site. How the three-tier split is computed lives in [`effort-ladder.md`](effort-ladder.md). Shipped per-role levels live in [`defaults.toml`](defaults.toml) and on plugin agent frontmatter.

Grok Build's model-facing `task` tool does **not** accept `reasoning_effort`. `TaskToolInput` at grok-build pin `c2ad97f87aea4303b6000a2c22128bc91ee76c9b` (`crates/common/xai-tool-types/src/task.rs`) has `prompt`, `description`, `subagent_type`, `run_in_background`, `isolation`, `resume_from`, `cwd`, `model`. Spawn from `task` sets `SubagentRuntimeOverrides.reasoning_effort` to `None` (`crates/codegen/xai-grok-tools/src/implementations/grok_build/task/mod.rs`).

The runtime that actually sets child sampling effort is `resolve_runtime_config` in `crates/codegen/xai-grok-subagent-resolution/src/definition.rs`:

1. `select_role(subagent_type)` looks up `[subagents.roles.<subagent_type>]` / `~/.grok/roles/<subagent_type>.toml` (`SubagentRole.reasoning_effort`).
2. Then persona (not a `task` field; model-facing spawn sets `persona: None`).
3. Then `AgentDefinition.effort` frontmatter, only if still unset.
4. Then inherit the parent session. `handle_request.rs` writes `effective_sampling_config.reasoning_effort` only when that resolved string parses as `ReasoningEffort`.

Do not send `reasoning_effort` on `task`. Plugin role agents **do** ship frontmatter `effort` so a fresh install with no setup still gets the ship-time split. A user overlay in `~/.grok/roles/pstack:<key>.toml` wins over that frontmatter.

## Spawn type

Set `subagent_type` to **`pstack:<role-key>`** on this TUI (`pstack:feature`, `pstack:how-explainer`, `pstack:independent-verifier`, …). grok 1.0.13 registers plugin agents as `plugin:name`. Bare `how-explorer` is rejected (`Unknown subagent type`) even when the plugin is enabled. Toml model keys stay the bare role key (`feature`). Overlay files are `~/.grok/roles/pstack:<key>.toml` so `select_role(subagent_type)` matches the spawn string. `/setup-pstack` writes that stem only.

This plugin ships an agent file per role key under `agents/`. Ad-hoc helpers with no role key: `pstack:poteto-agent`. `/no-comments` uses `pstack:comment-sicko`. Those two have no shipped `effort:` so they inherit the parent session.

If `pstack:<key>` is unknown this session, the plugin is not enabled (`grok plugin enable pstack` from a host shell; `inspect` "enabled" is trust, not `[plugins].enabled`). Fall back to `explore` (read-only) or `general-purpose` (writers / MCP / swarm) only after enable failed. That fallback **drops** per-role effort.

## Effort values at spawn

Spawn skills have **no API** to read the live grok-build effort enum. Do not probe `task.reasoning_effort`. Do not invent `ultra`. Follow this order:

1. Read `~/.grok/pstack-models.toml` if it exists. Look up `[effort].<role-key>`. Array model keys still have **one** scalar effort.
2. If that override file is **absent**, spawn the role key and stop. The plugin agent's frontmatter `effort` is the ship-time snapshot from [`effort-ladder.md`](effort-ladder.md). Do not expect a `~/.grok/roles` file. A later enum (for example `ultra`) is **not** applied until `/setup-pstack` re-detects and writes overlays.
3. If the override file exists and the key is missing, or the value is `inherit-parent` or `auto`, do **not** expect a role overlay (`/setup-pstack` deletes it). The child then uses plugin frontmatter `effort` (still the ship-time snapshot). Grok-build cannot inherit parent-session effort while `AgentDefinition.effort` is set, because spawn passes `None` and `apply_definition_runtime_defaults` fills from frontmatter.
4. If the value is a real effort token, `/setup-pstack` has written `~/.grok/roles/pstack:<role-key>.toml` with `reasoning_effort` set to that string. That overlay wins. Spawn `pstack:<role-key>`. Do not copy the string onto `task`.
5. Never invent a level. Never send `none`, `minimal`, or per-model menu ids such as `deep` from this plugin. Never send `max` unless `/setup-pstack` detected it on the live CLI `use one of:` list. Never send a token `/setup-pstack` did not detect this session.

`/setup-pstack` is the skill that re-resolves when the live enum differs from the ship-time snapshot. See [`effort-ladder.md`](effort-ladder.md).

This plugin is the Grok Build port. Out-of-box effort is `AgentDefinition.effort` on the role agent. Setup overlays are `SubagentRole.reasoning_effort`. Not a `task` field.
