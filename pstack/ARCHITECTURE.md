# PStack Gas City pack architecture

This pack is a mapping, not a second pstack. Two sources of truth stay distinct.

## Sources of truth

| Layer | Source | What it owns |
|---|---|---|
| Discipline and vendor | Official Cursor pstack at `https://github.com/cursor/plugins` path `pstack` commit `6fecddba65801f9b9c08b8b328d998ee5b09d290` | 21 principles, playbooks, method skills, plugin agent markdown. Listed vendor paths are skills, agents, README, LICENSE |
| Pack shape | gascity-packs methodology packs (`bmad`, `superpowers`, `gstack`, `compound-engineering`) | `pack.toml` imports `../gascity`, `*-build` extends `build-base`, selector formulas override pack-local assets |
| Primitives | `gascity/formulas` virtual contracts | `build-base`, `planning-base`, `decomposition-base`, `implementation-base`, `implementation-item-base`, `code-review-base`, `fix-loop-base`, `implement` |

Do not pin `tommy-ca/pstack`. That tree is a Grok Build port, not this pack's upstream. Do not treat Cursor `Task` fields or `watch-pr` as Gas City runtime. Those strings may exist in vendored Cursor playbooks. Pack-owned formulas and assets must not prescribe them.

## Building blocks from Cursor pstack

Map each official block to one Gas City surface.

| Cursor block | Gas City surface |
|---|---|
| `skills/principle-*` (21) | `pstack/skills/principle-*` plus `principles/manifest.toml` |
| `skills/poteto-mode/playbooks/*.md` | Runtime skill copy. Formulas select playbooks by formula identity, not `pstack.skill` metadata |
| `how`, `why`, `architect`, `swarm`, `arena`, `interrogate` | `pstack-how`, `pstack-why`, `pstack-architect`, `pstack-swarm`, `pstack-arena`, `pstack-interrogate` |
| Feature, bug-fix, refactor, perf, prototype | `pstack-feature`, `pstack-bug-fix`, `pstack-refactor`, `pstack-perf`, `pstack-prototype` extending `pstack-build` |
| Babysit, shipping, orchestrate, autonomous-run, autopilot | `pstack-babysit`, `pstack-shipping`, `pstack-orchestrate`, `pstack-autonomous-run`, `pstack-autopilot-*` extending `pstack-build` |
| `spawn_subagent` / Cursor `Task` | Gas City `gc.run_target` plus Beads claims. No provider task engine |
| `scripts/watch-pr`, `scripts/orch/orch.ts` | Cursor upstream text. Unsupported as Gas City runtime. Tests grep pack-owned formulas, assets, and agents |
| `agents/comment-sicko.md`, `agents/poteto-agent.md` | Host-plugin provenance under `vendor/pstack/agents/`. Not Gas City formulas. Pack-owned `pstack/agents/` stays `gc-role-worker` wrappers |

`make-bot-ui` exists in Cursor pstack 0.14.5 and is not a Gas City formula.

## Building blocks from gascity primitives

| Primitive | PStack formula | Override |
|---|---|---|
| `build-base` | `pstack-build` | Extra steps `principle-selection`, `subtract-assessment`, `foundation`, `lever-decision` |
| `planning-base` | `pstack-planning` | Pack-local requirements, plan, plan-review assets and `pstack.*` run targets |
| `decomposition-base` | `pstack-decomposition` | Extra step `lever-decision` before `decompose` |
| `implement` | `pstack-implementation` | Drain into `pstack-work` / `pstack-work-item` |
| `implementation-base` | `pstack-work` | Pack implementation convoy |
| `implementation-item-base` | `pstack-work-item` | Single work item |
| `code-review-base` | `pstack-review` | Expansion `pstack-build-review` |
| `fix-loop-base` | `pstack-fix-loop` | Pack review-fix loop |

Selector variables stay the six standard names. Mode vocabulary stays `interactive|autonomous|headless` and `report|agent|interactive`. Drain stays `separate|same-session`. `pstack-build` requirements and plan-review use the same `pstack.*` run targets as `pstack-planning`. Decompose still uses `gc.task-decomposer`. There is no pack-local decomposer role.

## Building blocks from workflow packs

Follow `bmad` and `superpowers` for packing, not for methodology content.

- Import `../gascity` as `gc`.
- Keep `schema = 2`.
- Extend `build-base`. Do not fork a private lifecycle.
- Override selector formulas with pack-local `description_file` and `gc.run_target`.
- Ship rig-scoped agents that wrap `gc-role-worker`.
- Prove compatibility through `gascity/tests/test_derived_pack_compatibility.py`.
- Use `[requires] formula_compiler = ">=2.0.0"`. Do not copy peer `contract = "graph.v2"`.

## Data shape

The pack is a registry of formulas, schemas, and source bindings.

- Formula TOML is the executable graph.
- `gc.build.*` schemas cover ordinary lifecycle artifacts.
- `pstack.*` schemas cover pack-only evidence.
- `vendor/pstack/` lists skills, agents, README, and LICENSE from Cursor `pstack/` at the recorded commit.
- Runtime `skills/` is a byte copy of vendored skills. It is methodology
  corpus, not formula `description_file`.
- Cursor plugin agents live under `vendor/pstack/agents/`. Pack-owned
  `pstack/agents/` are Gas City role wrappers. Guide docs and Benny
  automations are not vendored.

## Non-goals

- No second scheduler.
- No Cursor `Task` field names in formulas.
- No vendor refresh to a moving Cursor `main` SHA. The pin is commit `6fecddba`.
- No archive of `refresh-pstack-pack-source-and-formula-requirements` as written.
- No babysit or orchestrate detach from `pstack-build` in this change.
- No `graph_operator` interpreter.
