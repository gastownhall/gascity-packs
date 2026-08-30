# PStack

PStack is a Gas City methodology pack for principle-driven software change. It keeps durable execution in Gas City and Beads while adding a complete 21-principle policy layer, evidence schemas, providerless roles, and composable methods/programs.

## Use

```toml
[imports.pstack]
source = "../pstack"
```

Run `pstack-build` when the change follows the standard build lifecycle. Use `pstack-feature`, `pstack-bug-fix`, `pstack-refactor`, `pstack-migration`, `pstack-perf`, or `pstack-prototype` for explicit change shapes. `pstack-how`, `pstack-why`, `pstack-swarm`, `pstack-arena`, `pstack-interrogate`, `pstack-autonomous-run`, and `pstack-orchestrate` are composable formulas.

The pack imports Gas City's `build-base` and uses the shared `gc.build.*` schemas for ordinary lifecycle artifacts. PStack-specific artifacts cover foundation, lever decisions, reproduction/root cause, principle applications, candidate comparison, orchestration state, and revision-bound verification.

## Source boundary

The exact source corpus is under `vendor/pstack/` and is pinned in `vendor/pstack/upstream.toml`. Runtime-adapted roles, formulas, assets, mappings, schemas, and tests are outside the vendor tree. The pack includes all 21 principle skills; `principles/manifest.toml` is the machine-readable enforcement index.

## Safety

Pack tests are static or disposable metadata checks. They do not import into a canonical city, mutate live Beads, sling formulas, publish, push, or invoke provider-native orchestration.

See [`REQUIREMENTS.md`](REQUIREMENTS.md) for the GC-METH-012 compatibility
ledger and evidence commands.
