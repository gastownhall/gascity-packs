---
name: setup-pstack
description: Configure which models and reasoning effort pstack uses per role. Detects your available models and the live grok-build effort enum, then writes ~/.grok/pstack-models.toml plus ~/.grok/roles/pstack:<role>.toml. Use for /setup-pstack, "configure pstack models", or changing pstack's model or effort choices.
---

# Setup pstack

Write `~/.grok/pstack-models.toml` (model slugs and `[effort]`) and pstack-managed overlay files `~/.grok/roles/pstack:<key>.toml`. This is an **override layer**. A fresh install with no setup already uses the shipped default: `grok-4.6` plus per-role `effort` on the plugin agents (ship-time three-tier split in [`references/effort-ladder.md`](references/effort-ladder.md)). See [`references/defaults.toml`](references/defaults.toml), [`references/resolve-model.md`](references/resolve-model.md), and [`references/resolve-effort.md`](references/resolve-effort.md).

Skills read the toml for `task.model`. Grok Build applies effort from `~/.grok/roles/pstack:<role>.toml` when that overlay exists (`SubagentRole.reasoning_effort`), else from the plugin agent's frontmatter `effort`. Missing override file uses the shipped default. Missing key or `inherit-parent` or `auto` in an existing toml: omit `task.model`; delete the role overlay so frontmatter remains.

The models file is not a grok-build `[subagents.models]` table. That table maps agent types (`explore`, `plan`), not pstack roles. Never send `reasoning_effort` on `task`.

## Ask the human

This section is the only source for `ask_user_question`. Copy the option shape. Do not invent options. Do not quote **Agent only** into the TUI.

The question text, every option `label`, and every option `description` may use `inherit-parent`, `auto`, slugs from this session's detected set, effort tokens from this session's detected effort enum, pstack role key names, and plain words that explain those choices (every role, this chat's model, shipped default, grok-4.6, recommended split, mechanical, instruction-following, judgment, how-explainer, independent-verifier, customize per role, highest, one step down, two steps down). Nothing else. Do not put a level in the TUI that this session did not detect. Do not invent `ultra`. Do not offer `max` unless this session's live `use one of:` list named it.

### Models

First question. `questions[].question` is a short how-should-pstack-pick-models line. Options, in this order, and no others:

1. Shipped default (recommended), only if `grok-4.6` is in the detected set: `grok-4.6` for every role. Panel roles get one `grok-4.6` entry each.
2. `inherit-parent` for every role. Children use this chat's model.
3. One option per **other** detected slug. That slug for every role. On this box that is often `grok-4.5`. Use whatever step 1 actually detected. Do not add a slug that was not detected. Do not repeat `grok-4.6` here if it is already option 1.
4. Customize per role.

If `grok-4.6` was not detected, skip option 1. Then option 2 (inherit-parent) is first and recommended.

If they pick customize: follow-up questions, one role at a time or grouped. Each role's options are only `inherit-parent`, `auto`, and each detected slug.

Panel roles (`how-critics`, `arena-runners`, `arena-cross-judge-pool`, `architect-runners`, `interrogate-reviewers`) are arrays. Shipped default is one `grok-4.6` entry. Customize may add more entries. Each entry is still `inherit-parent`, `auto`, or a detected slug. One `task` spawn per entry.

### Effort

Second question, after models. Detect the live enum first ([`references/effort-ladder.md`](references/effort-ladder.md)). Compute the three-tier split from that list. `questions[].question` is a short how-should-pstack-pick-reasoning-effort line. Options, in this order, and no others:

1. Shipped default (recommended). Name the three resolved tokens this session. Highest detected for `judgment-and-prose`, `hardest-tasks`, `how-explainer`, `why-synthesizer`, `reflect-judgment`, `independent-verifier`, `how-critics`, `arena-runners`, `arena-cross-judge-pool`, `architect-runners`, `interrogate-reviewers`. One step down for `bug-fix`, `perf-issue`, `hillclimb`, `reflect-tooling`. Two steps down for `feature`, `refactoring`, `how-explorer`, `why-investigators`, `swarm-workers` (clamped off the weakest when the enum has three or more levels).
2. `inherit-parent` for every role. No `~/.grok/roles` overlay. Plugin agent frontmatter stays.
3. The **highest** detected level for every role. The option label is that token (whatever this session actually detected).
4. Customize per role.

If they pick customize: follow-up questions, one role at a time or grouped. Each role's options are only `inherit-parent`, `auto`, and each detected AgentDefinition level. Effort is one scalar per role even when the model key is an array.

Do not add `none`, `minimal`, or per-model menu ids such as `deep`. Do not add a token that was not detected. Do not offer `max` unless the live CLI listed it.

## Steps

### 1. Detect available models

Enumerate slugs the `task` tool accepts in `model` this session.

- Probe with an invalid `task.model` and read the rejection text for valid slugs.
- Run `grok models` if the CLI exposes it.
- Use `grok inspect --json` only if that JSON actually lists models. `InspectReport` often has no models field.

Never write a slug you have not confirmed this session. `inherit-parent` and `auto` are always valid and are not slugs: omit `model` on `task`.

### 1b. Detect the live effort enum

Follow [`references/effort-ladder.md`](references/effort-ladder.md). Do not send `reasoning_effort` on `task`.

- Prefer `grok --reasoning-effort not-a-real-effort` and the live `use one of:` list (`unknown effort level …; use one of: xhigh, high, medium, low` on grok 1.0.13). That list is strongest-first; reverse to weak → strong before stepping down.
- Do not use FromStr or `Effort::VALID_VALUES`. Those include reserved `max` that this CLI rejects.
- Else, only if `use one of:` never printed, parse `grok --help` for `--reasoning-effort` / `--effort`, canonical list only (before `also` / menu ids). Drop any help token the runtime list omitted.
- Drop `none`, `minimal`, and per-model menu ids such as `deep`.
- Do not invent `ultra`.
- Do not offer `max` unless this session's `use one of:` named it.
- Do not use the TUI effort menu as the set.
- If detection returns nothing, use the ship-time snapshot in that file (`low` `medium` `high` `xhigh`) and remember to say so in step 6, not in the TUI.

Compute the three-tier split from the detected (or snapshot) list. That computed table is the shipped-default effort option this session. It may differ from [`references/defaults.toml`](references/defaults.toml) if the live enum grew.

### 2. Load current state

If `~/.grok/pstack-models.toml` exists, read it (top-level model keys and `[effort]`). Otherwise the current state is [`references/defaults.toml`](references/defaults.toml) for models, and the **computed** three-tier split for `[effort]`. If `grok-4.6` is not in the detected set, treat every model key as `inherit-parent` while keeping that computed `[effort]` table. Do not load any other models file.

### 3. Map and confirm

Show every role with its current model and effort. Mark any real slug not in the detected set as needing a choice. Mark any `[effort]` token not in this session's detected effort enum as needing a choice. Confirm with `ask_user_question` using **Ask the human** above. Ask models first, then effort.

`arena-cross-judge-pool` is an array. Arena picks one value whose family differs from the parent when the file names more than one detected slug. `swarm-workers` is the default for every `/swarm` worker unless a race names a model per arm.

When they pick shipped-default models, write `grok-4.6` in every model key (one-entry arrays). When they pick inherit-parent models everywhere, write inherit-parent. When they pick one detected slug everywhere, write that slug. When they customize, write those choices.

When they pick shipped-default effort, write the **computed** `[effort]` table from step 1b (from this session's `use one of:` list, not VALID_VALUES and not a memorized max split). When they pick inherit-parent effort everywhere, write inherit-parent for every `[effort]` key. When they pick highest-everywhere or customize, write those `[effort]` values.

### 4. Validate

Every real slug must be in the detected set. `inherit-parent` and `auto` always pass. If a chosen slug is unavailable, ask again with the same allowed options. If they picked shipped-default models but `grok-4.6` is not detected, write inherit-parent for models instead.

Every `[effort]` value must be `inherit-parent`, `auto`, or a token from this session's detected effort enum. If not, ask again with the effort options above.

### 5. Write the files

Overwrite `~/.grok/pstack-models.toml` so re-runs stay idempotent.

Pstack-managed role files live at `~/.grok/roles/pstack:<role-key>.toml` so they match grok 1.0.13 spawn types (`pstack:feature`). Do not write a bare `~/.grok/roles/<role-key>.toml` stem. Create `~/.grok/roles/` if needed.

- If `[effort].<key>` is `inherit-parent` or `auto` or missing, **delete** those pstack-managed role files if they exist so a stale overlay cannot pin a different level than the plugin agent.
- If `[effort].<key>` is a detected AgentDefinition level, write only:

```toml
description = "pstack <role-key> role"
reasoning_effort = "<level>"
```

Do not write `model`, `prompt_file`, `default_capability_mode`, or `default_isolation` into those files. Do not edit `~/.grok/config.toml`. Do not delete role files whose names are not pstack keys.

First run writes the shipped default when they accept it. Copy [`references/defaults.toml`](references/defaults.toml) for **models**. Replace `grok-4.6` with `inherit-parent` only when `grok-4.6` was not detected this session. Replace the `[effort]` table with the computed live split when that split differs from the file.

EXAMPLE (ship-time snapshot). Same `[effort]` bytes as `references/defaults.toml` when the live usable set is `low` `medium` `high` `xhigh`. If this session's `use one of:` differed, write that computed table instead.

```toml
# Write only slugs detected this session (task.model rejection, grok inspect, grok models).
# grok-4.6 is the Grok Build shipped default. inherit-parent or auto: omit task.model.
# Missing key in an existing file: same as inherit-parent for models.
# Array keys: one task spawn per entry. Without a toml, skills send grok-4.6 (omit if rejected).
#
# [effort]: inherit-parent or auto or missing key: do not write ~/.grok/roles/pstack:<key>.toml.
# A detected AgentDefinition level: write ~/.grok/roles/pstack:<key>.toml with that reasoning_effort.
# Skills never send reasoning_effort on task. Spawn subagent_type = pstack:<role-key>.
# Plugin agents also ship frontmatter effort so a fresh install needs no setup.
# [effort] below is the ship-time three-tier split. Live detection may replace it.

feature = "grok-4.6"
refactoring = "grok-4.6"
bug-fix = "grok-4.6"
perf-issue = "grok-4.6"
hillclimb = "grok-4.6"
judgment-and-prose = "grok-4.6"
hardest-tasks = "grok-4.6"
how-explorer = "grok-4.6"
how-explainer = "grok-4.6"
how-critics = ["grok-4.6"]
why-investigators = "grok-4.6"
why-synthesizer = "grok-4.6"
reflect-tooling = "grok-4.6"
reflect-judgment = "grok-4.6"
arena-runners = ["grok-4.6"]
arena-cross-judge-pool = ["grok-4.6"]
swarm-workers = "grok-4.6"
architect-runners = ["grok-4.6"]
interrogate-reviewers = ["grok-4.6"]
independent-verifier = "grok-4.6"

[effort]
feature = "medium"
refactoring = "medium"
bug-fix = "high"
perf-issue = "high"
hillclimb = "high"
judgment-and-prose = "xhigh"
hardest-tasks = "xhigh"
how-explorer = "medium"
how-explainer = "xhigh"
how-critics = "xhigh"
why-investigators = "medium"
why-synthesizer = "xhigh"
reflect-tooling = "high"
reflect-judgment = "xhigh"
arena-runners = "xhigh"
arena-cross-judge-pool = "xhigh"
swarm-workers = "medium"
architect-runners = "xhigh"
interrogate-reviewers = "xhigh"
independent-verifier = "xhigh"
```

### 6. Confirm

Tell the user `~/.grok/pstack-models.toml` was written and that matching `~/.grok/roles/pstack:<key>.toml` files were added or removed. Name the detected effort enum and the three-tier map you wrote. If live detection failed and you used the ship-time snapshot, say that. New sessions pick them up. Re-running this skill updates them. Name those grok paths. Do not name other paths.

### 7. Offer a verification skill (optional)

Look for a `verify-*` skill under `.grok/skills/` or an existing harness. If neither exists, offer once via `ask_user_question` to generate one with `/create-verification-skill`. That question is yes or no. On yes, write `.grok/skills/verify-<app>/`. On no, move on.

## Agent only. Do not quote this section

Do not put any sentence from this section into `ask_user_question`, option labels, option descriptions, or the step 6 confirmation.

Write **only** `~/.grok/pstack-models.toml` and pstack-managed `~/.grok/roles/pstack:<key>.toml` files. Do not create `~/.cursor/rules/pstack-models.mdc` or any file under a Cursor rules directory.

Do not read `~/.cursor/rules/pstack-models.mdc`. If that file exists on disk, ignore it. It is not a source of defaults on Grok Build.

Proceed only on Grok Build: live `spawn_subagent` (`background`, `isolation`) and/or `grok` CLI. If this session would write Cursor rules paths, stop. Do not write those paths. Do not discuss that stop in the TUI. This plugin is the Grok Build port.

Do not copy an example table from another product, from older revisions of this skill, or from training memory. Models come from this session's detected set. Effort comes from [`references/effort-ladder.md`](references/effort-ladder.md) applied to this session's live `use one of:` list. Do not copy `Effort::VALID_VALUES`.

Do not offer a menu item that is not in **Ask the human**. Do not mention other products in the TUI. Do not offer to port or mix a mapping from another tool.
