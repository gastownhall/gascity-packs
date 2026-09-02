# PStack Pack Traceability

## Sources

| Source | Revision or locator | Use |
|---|---|---|
| Cursor pstack | `https://github.com/cursor/plugins/tree/main/pstack` commit `6fecddba65801f9b9c08b8b328d998ee5b09d290` | Canonical vendor corpus. Listed paths are skills, agents, README, and LICENSE. `docs/guide` is not copied |
| Workflow pack shape | gascity-packs `bmad`, `superpowers`, `gstack`, `compound-engineering` | Reference implementation for mapping a methodology onto `build-base` |
| Gas City primitives | `gascity/formulas` virtual contracts | `build-base` and selector bases the pack extends |
| Gist architecture | `23f21e688fc76b360d382e5cafb8d9c1` | Historical build-base, selector, formula, and schema notes |
| Repository OpenSpec | `openspec/specs/pstack-gascity-pack/spec.md` | Durable requirements, scenarios, architecture, ADR, and tasks |

The vendor remains intentionally pinned to this reviewed Cursor plugins
commit. Later Cursor `main` changes, including `README.md`,
`docs/guide/`, and `skills/poteto-mode/playbooks/`, are not silently imported.
`vendor/pstack/README.md` names the listed subset and the GitHub guide URL.
A future source refresh must use an OpenSpec change in this repository and
repeat the path/parity review. Do not treat a moving maintained SHA as the pack pin.
Do not pin `tommy-ca/pstack`.

OpenSpec change payloads do not live under `pstack/`. Durable Gherkin lives
at repository `openspec/`. Disposable live-city import is exercised when `GC_TEST_BIN` is set.
Formula sling of `pstack-poteto-mode` and `pstack-build` remains unproven.

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
| Dual source of truth | `ARCHITECTURE.md` | Cursor pstack for vendor corpus, gascity-packs workflow packs for packing |
| OpenSpec change payloads | not shipped under `pstack/` | Durable Gherkin is `openspec/specs/`. `scripts/apply_intent_change.py` refuses a `--source` inside the pack |
| Live program | `docs/pstack-program-plan.md` | Recursive task graph for isolation land, host sling, restamp, and later panel stamp |

## Evidence classes

- **Static:** TOML/YAML parse, source parity, formula metadata, schema references, provider-name absence.
- **Metadata:** inspectable formula TOML plus disposable live-city formula and agent listing. Validates declared node metadata only. There is no separate graph-cook script.
- **Runtime:** provider and live Gas City execution; not performed by pack-local verification.
- **Unavailable:** optional pack, provider, or live city not present; reported with a reason.

## Delivery boundary

Registry `0.1.0` is the first catalog pin. It is not a slung production release. Do not restamp `commit` or `hash` without a host sling of `pstack-poteto-mode` and `pstack-build`. `pstack-poteto-mode` classifies onto `pstack.route.v1` from `pstack/mappings/playbooks.toml`.
`pstack/scripts/validate_pstack_schemas.py` is the rerunnable schema inventory check. Run it with `uv run --with pyyaml python pstack/scripts/validate_pstack_schemas.py`.
It reuses Gas City `validate_schema_definition`. It does not require pydantic. Live city import and Formula sling remain independent host operations. OpenSpec validate and archive run against this repository `openspec/`.

## Known design gap

`pstack-swarm`, `pstack-arena`, and `pstack-interrogate` retain
`gc.graph_operator`/`pstack.graph_operator` metadata, but this checkout has no Gas City consumer
that gives those fields executable fanout semantics. The
current pack deliberately does not invent a second scheduler or provider
dispatch path. Do not interpret `graph_operator`. Swarm stays work-unit
annotation. The target for arena and interrogate N-model fanout is a city
`[[provider_panels]]` table plus a Gas City compiler that expands
`gc.provider_panel`. Durable specs live at `openspec/specs/`. Pack formulas
must not stamp `gc.provider_panel` until that consumer exists. This checkout
has no compiler consumer for `gc.provider_panel`.
