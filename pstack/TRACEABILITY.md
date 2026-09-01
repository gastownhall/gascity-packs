# PStack Pack Traceability

## Sources

| Source | Revision or locator | Use |
|---|---|---|
| Cursor pstack (discipline) | `https://github.com/cursor/plugins/tree/main/pstack` tree `6fecddba65801f9b9c08b8b328d998ee5b09d290` | 21 principles, playbooks, and method skills. Source of truth for upstream pstack |
| Runtime vendor | `tommy-ca/pstack` `49d6ae81f17125ac198efa322403490b366856b6` | Exact reviewed vendor corpus and runtime skill copy, including the Grok host-boundary correction |
| Workflow pack shape | gascity-packs `bmad`, `superpowers`, `gstack`, `compound-engineering` | Reference implementation for mapping a methodology onto `build-base` |
| Gas City primitives | `gascity/formulas` virtual contracts | `build-base` and selector bases the pack extends |
| Gist architecture | `23f21e688fc76b360d382e5cafb8d9c1` | Historical build-base, selector, formula, and schema notes |
| Dev-env OpenSpec | `dev-env/openspec/specs/pstack-gascity-pack/spec.md` | Durable requirements, scenarios, architecture, ADR, and tasks |

The vendor remains intentionally pinned to this reviewed snapshot. Maintained
PStack has later documentation and adapter-reference changes after that pin,
including `README.md`, `docs/guide/06-verify-and-ship.md`,
`docs/guide/13-grok-natives.md`,
`skills/poteto-mode/references/codex-tools.md`, and
`skills/poteto-mode/references/github-pr-fallback.md`. Those changes are not silently imported.
A future source refresh must use a separate intent change and repeat the
path/parity review. Do not treat a moving maintained SHA as the pack pin.

## Mapping

| Requirement | Implementation | Evidence |
|---|---|---|
| `pstack-build` extends `build-base` | `formulas/pstack-build.formula.toml` | Static formula inspection; compatibility test |
| Complete principle corpus | `skills/principle-*`, `principles/manifest.toml` | Set equality and manifest test |
| Shared lifecycle schemas | Imported `gc.build.*` metadata | Formula metadata test |
| PStack-only evidence | `schemas/*.yaml` | Schema ID and producer test |
| Providerless runtime | `agents/`, `assets/workflows/`, formula `gc.run_target` | Text and metadata tests |
| Durable orchestration boundary | `formulas/pstack-orchestrate.formula.toml` | No scheduler/database/session-manager test |
| Source/runtime separation | `vendor/pstack/` versus runtime assets | Source-binding/parity test |
| Dual source of truth | `ARCHITECTURE.md` | Cursor pstack for discipline, gascity-packs workflow packs for packing |
| Intent-driven spec payload | `intent/changes/audit-pstack-gascity-pack-contracts/` | `scripts/apply_intent_change.py --validate-only`; dest copy plus archive proven on a writable dest-env clone with no dropped requirements |

## Evidence classes

- **Static:** TOML/YAML parse, source parity, formula metadata, schema references, provider-name absence.
- **Metadata:** inspectable formula TOML plus disposable live-city formula and agent listing. Validates declared node metadata only. There is no separate graph-cook script.
- **Runtime:** provider and live Gas City execution; not performed by pack-local verification.
- **Unavailable:** optional pack, provider, or live city not present; reported with a reason.

## Delivery boundary

This checkout is prepared for review. Commit, push, pack publication, live import, canonical city mutation, Formula sling, and live Beads mutation remain independent operations.

## Known design gap

`pstack-swarm`, `pstack-arena`, and `pstack-interrogate` retain
`gc.graph_operator`/`pstack.graph_operator` metadata, but this checkout has no Gas City consumer
that gives those fields executable fanout semantics. The
current pack deliberately does not invent a second scheduler or provider
dispatch path; dynamic graph-operator behavior remains a separate Gas City
design change.
