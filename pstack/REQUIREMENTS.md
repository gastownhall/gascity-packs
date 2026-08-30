# PStack Gas City Pack Requirements

## Purpose

`pstack` is a Gas City methodology pack. It adds a principle-complete build policy and composable methods/programs while delegating durable execution, work claims, retries, workspaces, and observable state to Gas City and Beads.

## Required behavior

1. `pstack-build` extends `build-base`; it preserves the base anchors: prepare, requirements, plan, plan-review, decompose, implement, implement-same-session, summarize-implementation, review, finalize, publish.
2. The six standard selector variables and mode vocabulary remain available: `planning_formula`, `decomposition_formula`, `implementation_formula`, `implementation_item_formula`, `code_review_formula`, `review_fix_formula`; `interactive|autonomous|headless`; `report|agent|interactive`; `drain|convoy-step`; `separate|same-session`.
3. All 21 PStack principles are first-class runtime skills, listed exactly once in `principles/manifest.toml`, and each declares triggers, applicability, enforcement, and required artifacts.
4. Exact source is vendored at the immutable revision in `vendor/pstack/`; Gas City runtime adaptation is outside the vendor tree.
5. Ordinary lifecycle artifacts use the shared `gc.build.*` schemas. PStack-specific schemas are limited to evidence not represented by those shared schemas.
6. `how`, `why`, `investigation`, `swarm`, `arena`, `interrogate`, `autonomous-run`, and `orchestrate` are composable Gas City formulas, not a scheduler or replacement runtime.
7. Feature, bug-fix, refactor, migration, performance, prototype, shipping, babysit, and autopilot formulas compose the same Gas City graph contracts.
8. Bug-fix ordering is reproduce → root cause → plan → implementation → same-surface verification. Migration ordering includes caller inventory and legacy absence before final verification.
9. Large fanout requires a lever decision; novel multi-shape design uses Arena only when the trigger predicate is true.
10. Roles are providerless, use Gas City abstract run targets, and share the Gas City claim protocol.
11. Optional packs are optional composition inputs. Missing integrations produce an explicit skip/unavailable result and never block core pstack loading.

## Non-goals

- No second scheduler, database, session manager, event bus, or worktree manager.
- No provider-native dispatch instructions in runtime assets.
- No mutation of canonical `packs.lock`, `city.toml`, live Beads, or live Formula state as part of pack tests.
- No separate `gascity-packs-pstack` repository: this pack lives under the existing Gas City packs repository.

## Compatibility Claims

GC-METH-012: pstack is a derived Gas City methodology pack. It imports
`../gascity`, extends `build-base`, preserves the shared anchors/selectors,
uses Gas City graph fanout/drain contracts, and keeps provider/runtime
dispatch outside the pack.

## Evidence Commands

- `uv run --with pytest --with pyyaml pytest -q gascity/tests/test_formula_assets.py gascity/tests/test_derived_pack_compatibility.py pstack/tests/test_pstack_pack.py`
- `python -c 'import pathlib,tomllib; [tomllib.loads(p.read_text()) for p in pathlib.Path("pstack/formulas").glob("*.toml")]'`
- Disposable metadata cook with a temporary `GC_BEADS` backend; no canonical city mutation.
