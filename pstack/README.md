# PStack

PStack is a Gas City methodology pack for principle-driven software change. It keeps durable execution in Gas City and Beads while adding a complete 21-principle policy layer, evidence schemas, providerless roles, and composable methods/programs.

## When to choose pstack

- You want all 21 PStack principles enforced as Gas City gates, not as a
  Cursor plugin runtime.
- You want composable methods (`pstack-how`, `pstack-swarm`, `pstack-arena`,
  `pstack-interrogate`) on the same `build-base` contract as BMAD and Superpowers.
- Prefer `build-basic` when you want the default starter factory.
- Prefer `superpowers` when you want hard spec-approval gates and TDD.
- Prefer `bmad` when you want PRD and story readiness before code.

## Quick start

Prerequisites: Gas City installed and a city running, plus a git repository
registered as a rig.

1. **Import the pack.** From the city directory:

   ```sh
   gc import add https://github.com/gastownhall/gascity-packs.git//pstack
   ```

   Contributors working in this checkout can point `source` at `../pstack`
   instead, and the rig role import at `../gascity/roles`.

2. **Import the rig roles in `city.toml`.**

   ```toml
   [[rigs]]
   name = "proj"

   [rigs.imports.gc]
   source = "https://github.com/gastownhall/gascity-packs.git//gascity/roles"
   # local checkout: source = "../gascity/roles"
   ```

3. **Launch a build.** `pstack-build` is targeted. Create a bead, then sling:

   ```sh
   gc bd create "Add a --json flag to the export command"
   gc sling gc.run-operator <bead-id> --on pstack-build \
     --var artifact_root=plans/json-flag/build \
     --var drain_policy=separate
   ```

Run `pstack-feature`, `pstack-bug-fix`, `pstack-refactor`, `pstack-migration`,
`pstack-perf`, or `pstack-prototype` for explicit change shapes. `pstack-how`,
`pstack-why`, `pstack-swarm`, `pstack-arena`, `pstack-interrogate`,
`pstack-autonomous-run`, and `pstack-orchestrate` are composable formulas.

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
