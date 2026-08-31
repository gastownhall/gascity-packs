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

This tree is `tommy-ca/pstack`, a single-plugin repo. `plugin.json` `skills` lists `./skills/` and `./automations/benny-grok/skills/`. After enable, `/benny-triage` loads. There is no `commands/` directory and no `hooks` key. Do not nest this repo as `plugins/pstack`. The optional catalog is [tommy-ca/grok-build-plugins](https://github.com/tommy-ca/grok-build-plugins). Skills already are `/name`. xAI Official also lists a plugin named `pstack` that points at `cursor/plugins`. Do not use bare `grok plugin install pstack` as the default. Do not install `aa2246740/pstack-grokbuild` as the default. Parsed `plugin.json` fields and agent YAML rules are in [`HARNESS.md`](../../HARNESS.md) **Plugin schema**. That file is the host mapping `/poteto-mode` reads at the plugin root. It is not a plugin.json field. grok does not load it as a skill.

## Daily driver (sandbox)

Grok's everyday profile is **`workspace`**. It can write the current repo, `~/.grok/` (sessions, `installed-plugins/`, roles), and temp dirs. `18-sandbox.md`.

**homelab** is a custom profile (`~/.grok/sandbox.toml`) that extends `workspace` with extra writes (`~/.npm`, cache, `~/.local`). It does not add a full `~/.grok` deny. Under Linux bubblewrap the TUI still bind-mounts `config.toml`, `sandbox.toml`, and `hooks/` **read-only** (EROFS on `plugin enable`). That is the grok-build pin, not a pstack bug.

| Need | Driver |
|---|---|
| Edit this plugin's source | `workspace` or `homelab`. CWD is writable. Commit, then `grok plugin install /path/to/pstack --trust`. |
| Enable / marketplace / rewrite `config.toml` | Host shell: `grok --sandbox off plugin enable pstack`. |
| Tweak `~/.grok/roles/` or installed-plugins copies | Usually writable under `workspace`/`homelab`. Hooks dir stays write-denied. |
| Untrusted tree | `strict` or `read-only`. |

Do not set the daily driver to `off` just to enable a plugin. Use `off` only for that one host command. Do not weaken `workspace-secrets` denials of `.env`, keys, or `auth.json`.

Start pstack days with:

```bash
grok --sandbox workspace
```

Or keep `[sandbox] profile = "homelab"` if you need those extra write paths. Enable still uses `--sandbox off` once.

## How grok-native pstack works

This port is official pstack playbooks and 21 principles on Grok Build 1.0.13. It is not the Cursor plugin runtime.

**Router.** `/poteto-mode` matches a playbook and copies its steps into todos. It does not auto-enter. Skill order is pstack first, then user, then bundled and builtin. Example: `/tdd` before `/test-driven-development`.

**Spawn.** Children are `spawn_subagent` with `subagent_type` `pstack:<role>`. Example: `pstack:how-explorer`, `pstack:feature`, `pstack:independent-verifier`. Bare `how-explorer` is unknown. `MAX_SUBAGENT_DEPTH` is 1. This parent fans out. A child that spawns fails. After a writer joins, this parent runs `pstack:comment-sicko`. Do not send `reasoning_effort` on spawn. Effort is agent frontmatter or `~/.grok/roles/pstack:<key>.toml`.

**Join and overnight.** Join with `get_command_or_subagent_output`. `/loop` expands to `scheduler_create` (new turn, min 60s). Event wakes use `monitor`. Autopilot queues stay parent-fanout. They do not arm `/goal`.

**Benny.** `/benny-triage` loads after enable. Optional inbound: `grok -p '/benny-triage <permalink>'`. No Slack auto-start. No plugin `hooks`.

**Prove it.** `grok inspect --json` lists skills and `pstack:` agents only after enable. `grok plugin validate .` checks the manifest. Full mapping: [`HARNESS.md`](../../HARNESS.md). Natives we skip: [`13-grok-natives.md`](./13-grok-natives.md).

## Essential entries

Type `/poteto-mode` for rigor. Do not start from `/workflow` or `/goal`. Playbooks are not slash commands. The router matches them.

| Kind | Name | When |
|---|---|---|
| Router | `/poteto-mode` | Any checkable goal. Does not auto-enter. |
| Setup | `/setup-pstack` | Optional. Models and effort. |
| Build | `/tdd` `/unslop` `/no-comments` | After `/poteto-mode` picks Feature or Bug fix. Parent runs `/no-comments`. |
| How | `/how` `/why` | Read-only. Spawn `pstack:how-explorer`. |
| Benny | `/benny-triage` `/benny-repro` | Slack permalink after enable. |
| Spawn | `pstack:feature` `pstack:how-explorer` `pstack:independent-verifier` `pstack:comment-sicko` | Parent only. Depth 1. |
| Overnight | `/loop` | `scheduler_create`, new turn, min 60s. |
| Workflow | `/workflow` | Target repo `.grok/workflows/` only. Optional `agent_type: pstack:how-explorer`. Not a playbook clone. |
| Host | `grok inspect --json` `grok plugin validate` | Prove enable and the manifest. |

Twenty-two playbooks live under `skills/poteto-mode/playbooks/`. Common matches: Investigation, Feature, Bug fix, Autonomous run. Autopilot queues are parent-fanout. They do not arm `/goal`.

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

From here you can type normal follow-ups. Type `/poteto-mode` again when a playbook matches or the task needs rigor. It does not auto-enter. Opt out by saying so.

Next: [Route work through `/poteto-mode`](./02-poteto-mode.md).
