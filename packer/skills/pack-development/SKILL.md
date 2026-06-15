---
name: pack-development
description: Create and modify Gas City packs, including pack manifests, agents, skills, formulas, commands, and assets.
---

# Pack Development

Use this skill when editing a Gas City pack.

## Workflow

1. Inspect the pack tree and `pack.toml`.
2. Identify the artifact type being changed: agent, skill, formula, command,
   doctor check, template fragment, asset, or registry metadata.
3. Follow the existing naming style in that pack.
4. Keep new artifacts small enough to test directly.
5. Add or update tests when behavior changes.

## Artifact Boundaries

- Use `skills/` for model-facing workflow, safety rules, and domain knowledge.
  Route to references for long material instead of pasting it into prompts.
- Use `template-fragments/` for prompt sections shared by agents.
- Use `assets/` for scripts, examples, fixtures, static data, and generated
  files consumed by commands, formulas, tests, or prompts.
- Use `commands/` for direct operator actions that should be one CLI command.
- Use `formulas/` for multi-step operational workflows with vars, handoff,
  retry, validation, import, release, or live-city state.
- Use `agents/` for runtime roles. Canonical `gastown` polecat-style pools are
  agent templates with `min_active_sessions = 0` and `max_active_sessions = N`;
  do not make them `[[named_session]]` entries unless they are named runtime
  sessions.

## Pack Manifest

`pack.toml` must use schema 2:

```toml
[pack]
name = "example"
version = "0.1.0"
schema = 2
description = "Short purpose."
```

Named sessions should be explicit:

```toml
[[named_session]]
template = "worker"
scope = "rig"
mode = "on_demand"
```

## Agent Prompts

After changing `agents/<name>/prompt.template.md`, render it:

```bash
gc prime <name> --strict
```

If the prompt uses shared fragments, verify every `{{ template "..." . }}`
reference resolves.

## Formulas

After changing `formulas/*.toml`, compile the formula:

```bash
gc formula show <formula-name>
```

Use `gc formula cook` only when creating beads is intentional.

## Live Release

To make a pack live, publish a reachable commit, update the city import at the
right scope, install imports, and check the live render:

```bash
jj git push --bookmark <bookmark>
gc import add <github-tree-url> --name <binding> --version sha:<commit> --rig <rig>
gc import install
gc import check
gc prime <rig>/<agent> --strict
```

Avoid workspace-level imports for rig-scoped packs; duplicate bindings can hide
which version is live.