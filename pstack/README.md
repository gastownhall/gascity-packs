# PStack

PStack is a Gas City methodology pack for principle-driven software change. It keeps durable execution in Gas City and Beads while adding a complete 21-principle policy layer, evidence schemas, providerless roles, and composable methods/programs.

## When to choose pstack

- You want all 21 PStack principles enforced as Gas City gates, not as a
  Cursor plugin runtime.
- You want composable methods (`pstack-how`, `pstack-swarm`, `pstack-arena`,
  `pstack-interrogate`) as sequential Gas City graphs on the same `build-base`
  contract as BMAD and Superpowers. Gas City does not expand `gc.graph_operator`.
- Prefer `build-basic` when you want the default starter factory.
- Prefer `superpowers` when you want hard spec-approval gates and TDD.
- Prefer `bmad` when you want PRD and story readiness before code.

## Quick start

Prerequisites: Gas City installed and a city running, plus a git repository
registered as a rig.

```sh
brew install gascity
gc init ~/my-city
cd ~/my-city
gc start
mkdir proj && cd proj && git init
gc rig add .
```

1. **Import the pack.** From a local clone of this repository, in the city
   directory:

   ```toml
   [imports.pstack]
   source = "../gascity-packs/pstack"
   ```

   Point the rig role import at `../gascity/roles` or
   `../gascity-packs/gascity/roles`.

   The intended GitHub form is
   `gc import add https://github.com/gastownhall/gascity-packs.git//pstack`.
   That URL works only when the imported git ref contains `pstack/`. Registry
   `0.1.0` is a catalog pin, not a slung production release. Do not restamp it
   without a host sling.

2. **Import the rig roles in `city.toml`.** Then run `gc import install`:

   ```toml
   [[rigs]]
   name = "proj"

   [rigs.imports.gc]
   source = "https://github.com/gastownhall/gascity-packs.git//gascity/roles"
   ```

   ```sh
   gc import install
   ```

3. **Launch a build.** `pstack-build` is targeted. Create a bead, then sling:

   ```sh
   gc bd create "Add a --json flag to the export command"
   gc sling gc.run-operator <bead-id> --on pstack-build \
     --var artifact_root=plans/json-flag/build \
     --var drain_policy=separate
   ```

Run `pstack-feature`, `pstack-bug-fix`, `pstack-refactor` (alias
`pstack-refactoring`), `pstack-migration`, `pstack-perf` (alias
`pstack-perf-issue`), or `pstack-prototype` for explicit change shapes.
Method formulas `pstack-investigation`, `pstack-hillclimb`,
`pstack-runtime-forensics`, `pstack-trace-forensics`, `pstack-eval`,
`pstack-authoring-a-skill`, `pstack-session-pickup`,
`pstack-multi-phase-plan`, and `pstack-visual-parity` are sequential
evidence producers. They are not the full Cursor playbook graphs.
`opening-a-pr`, `pause-safely`, and `worktree-cleanup` stay unsupported as
sling formulas. `pstack-how`, `pstack-why`, `pstack-swarm`, `pstack-arena`,
`pstack-interrogate`, `pstack-autonomous-run`, and `pstack-orchestrate` are
composable formulas. Those method formulas are sequential annotated steps.
They are not Cursor child fanout. They are not multi-provider fanout.
This checkout still runs those methods as sequential graphs. N-model
routing belongs in city provider configuration, not in pack formula text
and not in a host Task spawn. Do not sling `/poteto-mode`. Sling `pstack-poteto-mode` to classify a request
into `pstack.route.v1`, then sling the `formula` field. The classifier does
not auto-sling.

## How N-model fanout will work

A city already maps one role to one provider with `[[rigs.patches]]`.
That table cannot give one role N backends. Duplicate patch rows are a
defect.

Target. The city declares `[providers.*]` catalog ids. Each id freezes
`--model` in `args`. Then a panel lists those ids, not model slugs.

```toml
[providers.cursor-grok]
base = "builtin:cursor"
args = ["--model", "cursor-grok-4.5-high", "--force"]

[[provider_panels]]
id = "pstack-arena"
members = ["cursor-grok", "cursor-composer", "antigravity"]
```

One catalog id cannot serve two models on Formula daemon work. A second
model needs a second `[providers.<id>]`. After Gas City consumes the key,
it will cook one child bead per member, isolate workspaces, and bind each
bead at dispatch. The pack will stamp `gc.provider_panel` and a
`{child_id}` artifact path only after that compiler exists.
`[session].provider` is the city session backend. It is not a panel member.
Sibling packs fan review personas, not models.

Until that consumer exists, sling `pstack-arena` and `pstack-interrogate`
as sequential evidence. Do not expect N isolated candidate files.

The pack imports Gas City's `build-base` and uses the shared `gc.build.*` schemas for ordinary lifecycle artifacts. PStack-specific artifacts cover foundation, lever decisions, reproduction/root cause, principle applications, candidate comparison, orchestration state, and revision-bound verification.

## Runtime schema context

Producer gates receive the resolved pack root through `GC_PACK_DIR`. The
shared `build-artifact-valid.sh` gate keeps the shared Gas City schema root
first, then adds `$GC_PACK_DIR/schemas` to `GC_BUILD_SCHEMA_ROOTS`; PStack
producers must not set `GC_BUILD_SCHEMA_ROOTS` directly. Relative artifact
paths use the gate's durable-root precedence: `GC_RIG_ROOT`,
`GC_BEADS_SCOPE_ROOT`, or `GC_DIR`, then an installed rig root, and finally
`GC_WORK_DIR` for source-tree or disposable-test contexts.

## Source boundary

The exact source corpus is official Cursor pstack under `vendor/pstack/`, pinned in `vendor/pstack/upstream.toml` to `cursor/plugins` path `pstack`. Listed paths are skills, plugin agents, README, and LICENSE. Runtime-adapted Gas City roles, formulas, assets, mappings, schemas, and tests are outside the vendor tree. The pack includes all 21 principle skills; `principles/manifest.toml` is the machine-readable enforcement index.

## Safety

Pack tests are static or disposable metadata checks. They do not import into a canonical city, mutate live Beads, sling formulas, publish, push, or invoke provider-native orchestration.

See [`REQUIREMENTS.md`](REQUIREMENTS.md) for the GC-METH-012 compatibility
ledger and evidence commands.
