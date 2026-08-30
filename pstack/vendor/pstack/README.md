# pstack

[English](README.md) · [简体中文](README.zh-CN.md)

This is a Grok Build port of official pstack. Playbooks and principles are poteto's; only the harness call layer is swapped.

## Credits

The 22 playbooks and 21 principles are [poteto](https://x.com/poteto)'s, from [official pstack](https://github.com/cursor/plugins/tree/main/pstack). This repository is **`tommy-ca/pstack`**, adapted from [aa2246740/pstack-grokbuild](https://github.com/aa2246740/pstack-grokbuild). Harness calls use Grok Build tools named in [HARNESS.md](./HARNESS.md). This port did not author those playbooks or principles.

poteto's idea is less slop, go deep first, and parallelize only after one agent can be trusted to write verifiable code. That philosophy is theirs. This README does not speak as poteto.

## Install

```bash
grok plugin install tommy-ca/pstack --trust
grok plugin enable pstack
```

xAI Official also lists a plugin named `pstack` that points at `cursor/plugins`. Use owner/repo. Do not treat bare `grok plugin install pstack` as this port.

A local checkout also works:

```bash
grok plugin install /path/to/pstack --trust
grok plugin enable pstack
```

## First session

1. Enable from a **host shell** if `grok plugin enable pstack` hits EROFS on `config.toml`:

   `grok --sandbox off plugin enable pstack`

   Or press Space in the Plugins tab. `inspect` "enabled" is trust. Skills and `pstack:<role>` agents load only when `pstack` is in `[plugins].enabled`.

2. Reload: Plugins tab `r`, or start a **new session**. This session will not grow `pstack:how-explorer` after enable.

3. Spawn `pstack:how-explorer`, not `how-explorer`. Type `/poteto-mode …`. It does not auto-enter. `/setup-pstack` is optional.

4. Do not run `grok plugin marketplace add` from a sandboxed agent. That also rewrites `config.toml` and hits EROFS. Owner/repo install still works in-session.

Tool mapping is in [HARNESS.md](./HARNESS.md).

## Get started

Two steps.

1. Use [`/poteto-mode`](./skills/poteto-mode/SKILL.md) for work that needs rigor. No setup required.
2. Optionally run [`/setup-pstack`](./skills/setup-pstack/SKILL.md) to change models or effort. It is optional and global. It writes `~/.grok/pstack-models.toml` plus `~/.grok/roles/pstack:<role>.toml`.

New here? The [pstack guide](./docs/guide/README.md) walks through a first real task, from setup and prompting through verification and overnight runs.

The other skills are situational. The mode skill uses them when a step needs them.

## Defaults

A fresh install is usable without `/setup-pstack`.

**Model.** Every role defaults to `grok-4.6`. If `spawn_subagent` rejects that slug, omit `model`. Do not invent Cursor panel slugs (`grok-4.6-fast-xhigh`, `gpt-5.6-sol-max`, `claude-fable-5-thinking-max`, `claude-opus-5-thinking-xhigh`). Spawn and join names are in [HARNESS.md](./HARNESS.md). The wire alias for `spawn_subagent` is `task`.

**effort.** Effort follows the live grok 1.0.13 CLI. `use one of: xhigh, high, medium, low`. Shipped split is judgment / explainer / verifier / panels `xhigh`, instruction-following `high`, mechanical `medium`. Do not ship `max`. This CLI rejects `max`. Skills never send `reasoning_effort` on `spawn_subagent`.

A missing override file uses the shipped default. A missing key, `inherit-parent`, or `auto` omits `model`. [`/setup-pstack`](./skills/setup-pstack/SKILL.md) re-detects from live `use one of:` and rewrites the split if it changed. Spawn skills cannot see a later enum. Run setup again if the binary grew a new level.

## Not the Cursor plugin

[`/setup-pstack`](./skills/setup-pstack/SKILL.md) in this repo configures model and effort for grok-build. Official Cursor `/setup-pstack` (inside Cursor, or the copy inside Grok Bot) is a different plugin. That copy writes `~/.cursor/rules` and uses Cursor slugs. Do not run it on Grok Build. It will not work here.

## Usage

Start a task with [`/poteto-mode`](./skills/poteto-mode/SKILL.md). It reads the request, picks a playbook, and runs the other skills as the steps need them.

### Use `/poteto-mode` directly

This is the main shortcut for rigorous engineering work. It ships twenty-two playbooks:

```
/poteto-mode this pr has a subtle bug where the scroll drifts every 750ms even when idle. repro
first, then fix and verify.
```

```
/poteto-mode i'm going to bed. land the stack even if ci flakes. i want everything merged by
morning.
```

<details>
<summary>the twenty-two playbooks</summary>

| playbook | for |
|---|---|
| [investigation](./skills/poteto-mode/playbooks/investigation.md) | a read-only question. how does x work, why was y built this way, are we sure. |
| [bug fix](./skills/poteto-mode/playbooks/bug-fix.md) | reproduce a defect, root-cause it, and fix with runtime evidence. |
| [perf](./skills/poteto-mode/playbooks/perf-issue.md) | trace a measured slowness and improve it against a baseline. |
| [hillclimb](./skills/poteto-mode/playbooks/hillclimb.md) | sustained, scientific improvement of one metric against a target, looping hypotheses with before/after measurement and one commit per accepted win. |
| [runtime forensics](./skills/poteto-mode/playbooks/runtime-forensics.md) | diagnose a live symptom (leak, idle-cpu spin, glitch) from instrumentation. |
| [trace forensics](./skills/poteto-mode/playbooks/trace-forensics.md) | diagnose a captured profiling artifact (cpuprofile, trace, spindump, heap snapshot). |
| [feature](./skills/poteto-mode/playbooks/feature.md) | new or changed behavior, built from a named data shape. |
| [refactoring](./skills/poteto-mode/playbooks/refactoring.md) | a behavior-preserving change to structure or shape. |
| [prototype](./skills/poteto-mode/playbooks/prototype.md) | a throwaway sketch to make a design or behavioral decision cheaply, or to settle an empirical fork by observing it. |
| [visual parity](./skills/poteto-mode/playbooks/visual-parity.md) | pixel-exact ui equivalence between two implementations. |
| [authoring a skill](./skills/poteto-mode/playbooks/authoring-a-skill.md) | writing or editing a SKILL.md. |
| [eval](./skills/poteto-mode/playbooks/eval.md) | test how a skill or prompt change affects agent behavior, blinded. |
| [babysit](./skills/poteto-mode/playbooks/babysit.md) | drive a pr or a stack to merge-ready: conflicts, review threads, ci. |
| [shipping](./skills/poteto-mode/playbooks/shipping.md) | independently verify a green stack, then land the contiguous verified run with graphite merge-when-ready. |
| [autonomous run](./skills/poteto-mode/playbooks/autonomous-run.md) | drive a long task to completion without stopping. |
| [orchestrate](./skills/poteto-mode/playbooks/orchestrate.md) | a standing project handed to one coordinator chat: multi-day, many stacked prs, fleets of subagents. |
| [autopilot-full](./skills/poteto-mode/playbooks/autopilot-full.md) | run independent prs to merged with one owner per pr and root verification of each merge-ready head. |
| [autopilot-stack](./skills/poteto-mode/playbooks/autopilot-stack.md) | build and verify one linear graphite stack for the operator to review and land. |
| [session pickup](./skills/poteto-mode/playbooks/session-pickup.md) | resume or take over a prior agent's in-flight work. |
| [pause safely](./skills/poteto-mode/playbooks/pause-safely.md) | suspend in-flight work cleanly so it can be resumed later. |
| [multi-phase plan](./skills/poteto-mode/playbooks/multi-phase-plan.md) | work that spans phases or stacked PRs. |
| [worktree cleanup](./skills/poteto-mode/playbooks/worktree-cleanup.md) | reclaim disk by pruning merged or abandoned worktrees and stale ios simulators, safety-gated. |

</details>

When invoked it:

1. opens a todo list. the first item is reading the inline principles index in the skill.
2. matches your task to a [playbook](./skills/poteto-mode/playbooks/) and copies the steps in verbatim.
3. routes to the other skills as the steps fire.
4. writes unslopped replies framed for the consumer and the maintainer.

The full rules and playbooks live in [`skills/poteto-mode/SKILL.md`](./skills/poteto-mode/SKILL.md).

[`/poteto-mode`](./skills/poteto-mode/SKILL.md) is also a sticky mode. Once entered it stays on across turns, applying itself when a playbook matches or the task needs rigor, and staying out of the way otherwise. Opt out any time by saying so.

[`/poteto-mode`](./skills/poteto-mode/SKILL.md) works with grok-build `/loop`, which expands to `scheduler_create`. You can leave a checkable predicate running for hours without sacrificing rigor.

## Skills

[`/poteto-mode`](./skills/poteto-mode/SKILL.md) runs most of these for you when a step needs them (`how`, `why`, `architect`, `arena`, `swarm`, `interrogate`, `unslop`, `no-comments`, `technical-writing`, `tdd`, and the principles). The table below is for when you want one directly:

```
/how do we cancel runs? do we have an n+1 when we look up every run to cancel?
```

```
/interrogate review this pr.
```

<details>
<summary>all skills</summary>

| skill | use it when |
|---|---|
| [`/poteto-mode`](./skills/poteto-mode/SKILL.md) | default entry point for any non-trivial task. |
| [`/how`](./skills/how/SKILL.md) | you want a walkthrough of how a subsystem works. |
| [`/why`](./skills/why/SKILL.md) | you want to know why something was built this way. discovers available MCPs at run time and queries each evidence category in parallel (source control, issue tracker, long-form docs, real-time chat, infra observability, error tracking, analytics warehouse). |
| [`/recall`](./skills/recall/SKILL.md) | you're starting or resuming work and want your recent context on a topic rebuilt from your own chat history and the shared record, handed back as a tight current-state brief. |
| [`/blast-radius`](./skills/blast-radius/SKILL.md) | you have a small-looking change and want to know what else it could break, with the one fact it's safe because of proven by running code, not asserted. |
| [`/architect`](./skills/architect/SKILL.md) | you're about to write code that crosses a function boundary and want the caller's usage, types, and module shape settled first. |
| [`/arena`](./skills/arena/SKILL.md) | you want N parallel attempts at the same thing, then to grab the best parts of each. |
| [`/swarm`](./skills/swarm/SKILL.md) | you want N parallel workers across different slices or races, then one aggregated report. |
| [`/interrogate`](./skills/interrogate/SKILL.md) | you have a diff and want several different models to try to break it, including a strict code-quality lens. |
| [`/automate-me`](./skills/automate-me/SKILL.md) | you want your own `-mode` skill, drafted from how you've actually worked. |
| [`/setup-pstack`](./skills/setup-pstack/SKILL.md) | override the shipped `grok-4.6` + per-role effort default. detects your models and writes `~/.grok/pstack-models.toml` plus `~/.grok/roles/pstack:<role>.toml`. |
| [`/reflect`](./skills/reflect/SKILL.md) | a long task landed and you want the recipe captured as a skill edit. |
| [`/teach`](./skills/teach/SKILL.md) | you want to actually understand a change or subsystem, not just have it summarized. runs how + why and weaves one plain explanation, built up diagram by diagram. |
| [`/tdd`](./skills/tdd/SKILL.md) | you're fixing a bug and there's a cheap local test path. write the failing test first, then the fix. |
| [`/no-comments`](./skills/no-comments/SKILL.md) | strip comments before review; spawns Comment Sicko, fixes accepted findings, offers encodings for claimed constraints. |
| [`/typescript-best-practices`](./skills/typescript-best-practices/SKILL.md) | you're reading or editing typescript. grounds the type-system-discipline principle in syntax. |
| [`/figure-it-out`](./skills/figure-it-out/SKILL.md) | no bundled playbook fits. designs a rigorous, auditable playbook for the task. |
| [`/show-me-your-work`](./skills/show-me-your-work/SKILL.md) | you want a reviewable decision trail. logs decisions to a tsv you can commit. |
| [`/create-verification-skill`](./skills/create-verification-skill/SKILL.md) | your project has no scripted way to prove app behavior. generates a project-local verify skill with a feature map, for any language or platform. |
| [`/maintain-verification-skill`](./skills/maintain-verification-skill/SKILL.md) | your verify skill's feature map has drifted from the app. source wave + one live pass, at most one PR of proven corrections. |
| [`/unslop`](./skills/unslop/SKILL.md) | you're cleaning up writing. removes AI tells. |
| [`/bro`](./skills/bro/SKILL.md) | you want the last message restated in plain human language, no jargon. |
| [`/technical-writing`](./skills/technical-writing/SKILL.md) | layered doc standard (Diátaxis + Google developer style + STE + Global English) for docs, RFCs, readmes, PR descriptions, commit messages. |

</details>

### Examples

Most tasks start with [`/poteto-mode`](./skills/poteto-mode/SKILL.md) and let it route to a playbook. The other skills fire as the steps need them. A few are worth invoking directly.

<details>
<summary>all the examples</summary>

```
bug fix:           /poteto-mode this pr has a subtle bug where the scroll drifts every 750ms even
                   when idle. repro first, then fix and verify.
perf:              /poteto-mode a big list takes a second or two to load even though we virtualize.
                   run a cpu trace and tell me why.
feature:           /poteto-mode build a small feature behind a feature flag. verify it really works.
prototype:         /poteto-mode build two prototypes of the markdown renderer so we can compare.
                   spawn an agent for each.
multi-phase:       /poteto-mode open source these skills as a plugin. nothing internal leaks, work
                   in a temp dir, show me the dependency graph first.
overnight run:     /poteto-mode i'm going to bed. land the stack even if ci flakes. i want
                   everything merged by morning.
babysit:           /poteto-mode check on pr 123. anything outstanding?
visual parity:     /poteto-mode the row spacing is too tall when this flag is on. the second image
                   is correct. repro and fix until it matches.
figure it out:     /poteto-mode i'm stepping away. migrate every caller from the synchronous store
                   to the new async one, keeping behavior identical. i want to trust it was done
                   right when i'm back.
how:               /how do we cancel runs? do we have an n+1 when we look up every run to cancel?
why:               /why is this feature flag not on yet?
architect:         design this instrumentation to be high signal with no false positives. /architect
                   this first.
arena:             /arena take my prompt to the arena verbatim. i want to compare their proposals
                   with yours.
swarm:             /swarm check every package under packages/ against its check.sh. one worker per
                   package. one report.
interrogate:       /interrogate review this pr.
tdd:               /tdd implement
unslop:            can we unslop and tighten the new changes?
reflect:           /reflect that took too long. capture what we learned so the next run doesn't
                   repeat it.
show-me-your-work: /show-me-your-work keep a decision trail i can review when i'm back.
automate-me:       /automate-me
```

</details>

## poteto-agent and Comment Sicko

This plugin also ships a subagent that runs the style end to end. Spawn it from the parent via `spawn_subagent` with `subagent_type: "pstack:poteto-agent"` when there is no role key. The wire alias for `spawn_subagent` is `task`. Playbook roles spawn `pstack:<role-key>` (`pstack:feature`, `pstack:how-explainer`, …) so shipped frontmatter `effort` applies, and so `/setup-pstack` overlays in `~/.grok/roles/pstack:<key>.toml` can override it. Substituting `general-purpose` skips the poteto-mode read and drifts. The child cannot spawn further children (`MAX_SUBAGENT_DEPTH` is 1). Do not send `reasoning_effort` on `spawn_subagent`.

[`/poteto-mode`](./skills/poteto-mode/SKILL.md) and [`subagent_type: "pstack:poteto-agent"`](./agents/poteto-agent.md) route through the same wrapper.

This plugin also ships [Comment Sicko](./agents/comment-sicko.md), a read-only comment reviewer available as `subagent_type: "pstack:comment-sicko"`. Usually invoke it through [`/no-comments`](./skills/no-comments/SKILL.md), not directly.

## Principles

Twenty-one short skills, one principle each. `poteto-mode` indexes them inline and reads that index at task start. The standalone files are there so other skills can reference a principle by name, and so the index can point at the full rule for each.

<details>
<summary>all twenty-one principles</summary>

| principle | group | rule |
|---|---|---|
| [laziness-protocol](./skills/principle-laziness-protocol/SKILL.md) | core | Bias toward deletion and the smallest change that solves the problem. |
| [foundational-thinking](./skills/principle-foundational-thinking/SKILL.md) | core | Apply before writing logic: choosing core types and data structures, sequencing scaffold-vs-feature work, asking what concurrent actors share. Get the data structures right so downstream code becomes obvious. |
| [redesign-from-first-principles](./skills/principle-redesign-from-first-principles/SKILL.md) | core | Redesign as if the requirement had been a foundational assumption from day one, instead of bolting it on. |
| [subtract-before-you-add](./skills/principle-subtract-before-you-add/SKILL.md) | core | Remove dead weight, redundant validators, and stub references first, then build on the simpler base. |
| [minimize-reader-load](./skills/principle-minimize-reader-load/SKILL.md) | core | Count layers between question and answer, and hidden state in the reader's head; collapse one-caller wrappers and shrink mutable scope. |
| [outcome-oriented-execution](./skills/principle-outcome-oriented-execution/SKILL.md) | core | Apply during planned rewrites and migrations with explicit phase boundaries. Converge on the target architecture; don't preserve smooth intermediate states with throwaway compatibility code. |
| [experience-first](./skills/principle-experience-first/SKILL.md) | core | Choose user delight over implementation convenience; ship fewer polished features over more rough ones. |
| [exhaust-the-design-space](./skills/principle-exhaust-the-design-space/SKILL.md) | core | Build 2-3 competing prototypes and compare side by side before committing. |
| [build-the-lever](./skills/principle-build-the-lever/SKILL.md) | core | Apply to any non-trivial work, not just bulk work: edits, migrations, analyses, checks. Build the tool that does it or proves it (codemod, script, generator, or a skill your subagents follow) instead of working by hand. The tool is the artifact a reviewer can rerun. |
| [model-the-domain](./skills/principle-model-the-domain/SKILL.md) | architecture | Encode the domain in a structure instead of scattered conditionals. |
| [boundary-discipline](./skills/principle-boundary-discipline/SKILL.md) | architecture | Concentrate guards at system boundaries (CLI, config, network, external APIs); trust internal types and keep business logic in pure functions. |
| [type-system-discipline](./skills/principle-type-system-discipline/SKILL.md) | architecture | Make illegal states unrepresentable, brand semantic primitives, parse external data at boundaries, refuse to lie to the compiler, exhaust variants, derive from authoritative schemas. |
| [make-operations-idempotent](./skills/principle-make-operations-idempotent/SKILL.md) | architecture | Converge to the same end state regardless of partial prior runs. |
| [migrate-callers-then-delete-legacy-apis](./skills/principle-migrate-callers-then-delete-legacy-apis/SKILL.md) | architecture | Migrate callers and delete the old API in the same wave instead of preserving compatibility layers. |
| [separate-before-serializing-shared-state](./skills/principle-separate-before-serializing-shared-state/SKILL.md) | architecture | Eliminate the sharing first; serialize structurally only when one shared writer is a real invariant. |
| [prove-it-works](./skills/principle-prove-it-works/SKILL.md) | verification | Apply after completing a task, before declaring done. Verify against the real artifact (run the feature, read the actual value, inspect the diff), not a proxy, self-report, or 'it compiles.'. |
| [fix-root-causes](./skills/principle-fix-root-causes/SKILL.md) | verification | Trace each symptom to its root cause and fix it there; reproduce first, ask why until you reach it, resist nil-check guards that silence crashes. |
| [sequence-verifiable-units](./skills/principle-sequence-verifiable-units/SKILL.md) | verification | Apply to multi-step work (sweeps, migrations, runs of similar edits) and to how you stack commits and PRs. Break work into small units that each end in a verifiable state, check each before the next, and order delivery so the sequence proves itself to a reviewer. |
| [guard-the-context-window](./skills/principle-guard-the-context-window/SKILL.md) | delegation | Route bulk to subagents; keep summaries in the main thread, not raw payloads. |
| [never-block-on-the-human](./skills/principle-never-block-on-the-human/SKILL.md) | delegation | Proceed, present the result, let the human course-correct after the fact; reserve confirmation for irreversible actions. |
| [encode-lessons-in-structure](./skills/principle-encode-lessons-in-structure/SKILL.md) | meta | Encode the rule as a lint, metadata flag, runtime check, or script instead of more text. |

</details>

## Not shipped here

A few things `poteto-mode` referenced in Cursor pstack and does not bundle here:

- `/deslop`, `control-cli`, and `control-ui` lived in `cursor-team-kit`. Use `/unslop`, `/no-comments`, and drive the real app yourself.
- Independent verify is `spawn_subagent` + `independent-verifier`. Send a different `model` when the toml names a detected slug; otherwise omit `model`. Not a Cursor Cloud Agent. See [HARNESS.md](./HARNESS.md).
- Graphite `gt` is optional. If it is missing, use `gh` and git.
- Benny remains under `automations/benny/` as source. Grok Build automations are plugin hooks/workflows, not this pack.

## Why are there no planning skills?

grok-build has a built-in `plan` agent type. pstack still does not default to planning. The best spec is code. If you do want a plan, [`/poteto-mode`](./skills/poteto-mode/SKILL.md) covers it.

## Make it yours

`poteto-mode` is poteto's style. You may not want exactly that.

Type [`/automate-me`](./skills/automate-me/SKILL.md). It mines recent transcripts, drafts a `<your-name>-mode` skill from how you have actually worked, and routes through pstack underneath. You keep pstack as the base and end up with your own routing skill alongside `poteto-mode`.

The Grok Build default is `grok-4.6` plus per-role effort. Type [`/setup-pstack`](./skills/setup-pstack/SKILL.md) only if you want to change that. It detects slugs `spawn_subagent` accepts, asks for reasoning effort per role, and writes `~/.grok/pstack-models.toml` plus pstack-managed `~/.grok/roles/pstack:<role>.toml`. It will not write `~/.cursor/rules`. This is not the Cursor plugin.

## Automations

This repo also ships a dormant [benny automation pack](./automations/benny/). It is Cursor automation source, not a Grok Build hook pack. Its files are not registered as slash skills. The Grok equivalent is plugin `hooks/` plus workflows. Not wired in this port.

Fork it. Improve it. PRs are welcome.

## License

MIT.

Upstream is official pstack / poteto (Lauren Tan). This repository is **`tommy-ca/pstack`**, adapted from [aa2246740/pstack-grokbuild](https://github.com/aa2246740/pstack-grokbuild).
