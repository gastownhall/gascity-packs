# Set up pstack

In this page you install the plugin, optionally pick models and reasoning effort, and run your first task. A fresh install already uses `grok-4.6` plus per-role effort. Setup is one command plus a short conversation if you want to change that.

## Install the plugin

```bash
grok plugin install tommy-ca/pstack --trust
grok plugin enable pstack
```

## First session

1. If enable hits EROFS on `config.toml`, run it from a **host shell**: `grok --sandbox off plugin enable pstack`. Or press Space in the Plugins tab. `inspect` "enabled" is trust, not `[plugins].enabled`.
2. Reload: Plugins tab `r`, or start a **new session**. Spawn types are a session-start snapshot.
3. After enable, `grok inspect --json` `.agents[].name` is `pstack:how-explorer`, not `how-explorer`. Type `/poteto-mode`. It does not auto-enter. `/setup-pstack` is optional.
4. Do not run `grok plugin marketplace add` from a sandboxed agent (same EROFS). Owner/repo install still works in-session.

This tree is `tommy-ca/pstack`. The plugin ships `skills/` and `agents/` only. There is no `commands/` directory. Skills already are `/name`. xAI Official also lists a plugin named `pstack` that points at `cursor/plugins`. Do not use bare `grok plugin install pstack` as the default. Do not install `aa2246740/pstack-grokbuild` as the default. Parsed `plugin.json` fields and agent YAML rules are in [`HARNESS.md`](../../HARNESS.md) **Plugin schema**.

## Pick your models and effort (optional)

The Grok Build default is `grok-4.6` for every role and a three-tier effort split on the plugin agents (ship-time `xhigh` / `high` / `medium`, from the grok 1.0.13 CLI usable set). You can start working without `/setup-pstack`. `/setup-pstack` re-detects from live `use one of:` and rewrites that split if it changed. It does not offer `max` unless that list named it.

To override, run:

```text
/setup-pstack
```

[`/setup-pstack`](../../skills/setup-pstack/SKILL.md) detects slugs `spawn_subagent` accepts, asks with `ask_user_question`, and writes `~/.grok/pstack-models.toml` plus `~/.grok/roles/pstack:<role>.toml`. It never writes a Cursor rules file. Spawn, join, and overnight field names are in [`HARNESS.md`](../../HARNESS.md).

This repo is the Grok Build port. Official Cursor `/setup-pstack` still writes `~/.cursor/rules`. Do not run that copy here.

A missing override file uses the shipped default. Run `/setup-pstack` again to change it.

## Accept the verification offer, or don't

At the end of setup, `/setup-pstack` looks for a way to prove app behavior, either a `verify-*` skill under `.grok/skills/` or an existing harness. If it finds neither, it offers once to generate one with [`/create-verification-skill`](../../skills/create-verification-skill/SKILL.md).

Say yes and it writes `.grok/skills/verify-<app>/`. Say no and setup moves on.

After setup, start a new session. The model file applies.

## Run your first task

Pick something real but small, and describe it the way you'd describe it to a colleague:

```text
/poteto-mode add a --json flag to this command. text output stays byte-identical. verify both.
```

Watch the todo list. The first item is always read the Principles section and [`HARNESS.md`](../../HARNESS.md) (the Grok mapping file). The rest are the matched playbook's steps copied in, the Feature playbook for this prompt. If `/poteto-mode` skips a step, the step stays in the list with `skip: <reason>`, so you can see what it chose not to do.

From here you can type normal follow-ups. `/poteto-mode` is sticky. It stays on for the conversation until you opt out by saying so.

Next: [Route work through `/poteto-mode`](./02-poteto-mode.md).
