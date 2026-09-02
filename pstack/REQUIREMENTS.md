# PStack Gas City Pack Requirements

## Purpose

`pstack` is a Gas City methodology pack. It adds a principle-complete build policy and composable methods/programs while delegating durable execution, work claims, retries, workspaces, and observable state to Gas City and Beads.

## Required behavior

1. `pstack-build` extends `build-base`; it preserves the base anchors: prepare, requirements, plan, plan-review, decompose, implement, implement-same-session, summarize-implementation, review, finalize, publish.
2. The six standard selector variables and mode vocabulary remain available: `planning_formula`, `decomposition_formula`, `implementation_formula`, `implementation_item_formula`, `code_review_formula`, `review_fix_formula`; `interactive|autonomous|headless`; `report|agent|interactive`; `drain|convoy-step`; `separate|same-session`. `pstack-planning` and `pstack-decomposition` override pack-local assets and `pstack.*` run targets the way sibling methodology packs do. `pstack-decomposition` includes `lever-decision` before `decompose`.
3. All 21 PStack principles are first-class runtime skills, listed exactly once in `principles/manifest.toml`, and each declares triggers, applicability, enforcement, and required artifacts.
4. Canonical vendor is Cursor pstack at `https://github.com/cursor/plugins` path `pstack` commit `6fecddba65801f9b9c08b8b328d998ee5b09d290`. Listed vendor paths are skills, agents, README, and LICENSE. Do not pin `tommy-ca/pstack`. Packing follows gascity-packs workflow packs on Gas City primitives. See `ARCHITECTURE.md`.
5. Ordinary lifecycle artifacts use the shared `gc.build.*` schemas. PStack-specific schemas are limited to evidence not represented by those shared schemas; every PStack schema declares the shared coverage-status vocabulary and `producer.attempt` front matter.
6. `how`, `why`, `investigation`, `swarm`, `arena`, `interrogate`, `autonomous-run`, and `orchestrate` are composable Gas City formulas, not a scheduler or replacement runtime.
6a. Multi-model arena and interrogate fanout is Gas City provider routing. Pack formulas stay providerless and MUST NOT name provider ids or model slugs. The city lists panel members under `[[provider_panels]]` once Gas City consumes `gc.provider_panel`. Members MUST be `[providers.<id>]` catalog ids. Members MUST NOT be model slugs (`composer-2.5`, `cursor-grok-4.5-high`) or `[session].provider`. One catalog id carries one frozen model via provider `args`. A second model requires a second catalog id. Formula-managed daemon work MUST NOT select `--model` per child. Until that consumer exists, this checkout MUST NOT stamp `gc.provider_panel`. Sequential formulas and inert `gc.graph_operator` annotation remain. N writers MUST NOT share one artifact path. Sibling pack review expansions remain persona lanes, not N-model. Durable Gherkin lives in this repository under `openspec/`.
7. Feature, bug-fix, refactor, migration, performance, prototype, shipping, babysit, and autopilot formulas compose the same Gas City graph contracts.
8. Bug-fix ordering is reproduce → root cause → plan → implementation → same-surface verification. Migration ordering includes caller inventory and legacy absence before final verification.
9. Large fanout requires a lever decision; novel multi-shape design uses Arena only when the trigger predicate is true.
10. Roles are providerless, use Gas City abstract run targets, and share the Gas City claim protocol.
11. Optional packs are optional composition inputs listed in `mappings/optional-packs.toml`. Missing optional packs never block core pstack loading.

## Non-goals

- No second scheduler, database, session manager, event bus, or worktree manager.
- No provider-native dispatch instructions in runtime assets.
- No mutation of canonical `packs.lock`, `city.toml`, live Beads, or live Formula state as part of pack tests.
- No separate `gascity-packs-pstack` repository: this pack lives under the existing Gas City packs repository.
- No OpenSpec change payloads under `pstack/`. Durable Gherkin lives at repository `openspec/`.

## Compatibility Claims

GC-METH-012: pstack is a derived Gas City methodology pack. It imports
`../gascity`, extends `build-base`, preserves the shared anchors/selectors,
uses Gas City graph drain contracts and annotated `graph_operator` metadata,
and keeps provider/runtime dispatch outside the pack.

## Evidence Commands

- `uv run --with pytest --with pyyaml pytest -q gascity/tests/test_formula_assets.py gascity/tests/test_derived_pack_compatibility.py pstack/tests/test_pstack_pack.py`
- `python -c 'import pathlib,tomllib; [tomllib.loads(p.read_text()) for p in pathlib.Path("pstack/formulas").glob("*.toml")]'`
- Disposable live-city formula and agent listing when `GC_TEST_BIN` is set; no canonical city mutation. Formula sling of `pstack-poteto-mode` and `pstack-build` remains unproven.
- `python pstack/scripts/apply_intent_change.py --source openspec/changes/archive/2026-09-02-pstack-program-arm-list --validate-only` validates against this repository `openspec/`. The change name is the `--source` directory with a leading date prefix stripped. `--dest` defaults to the repository root. `--archive` merges into `openspec/specs/`. New payloads live under `openspec/changes/`. They do not live under `pstack/` or `docs/openspec-changes/`.
