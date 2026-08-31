# PStack Pack Traceability

## Sources

| Source | Revision or locator | Use |
|---|---|---|
| PStack source | `74b1200c596102d051bd0fd3aa6dea68148be870` | Exact vendor corpus and 44 runtime skill directories |
| Gist architecture | `23f21e688fc76b360d382e5cafb8d9c1` | Corrected build-base, selector, formula, and schema requirements |
| Gas City packs | `9f98ea4e1974cb49d18cd0c453eb81b2370cca84` | Pack and derived-formula contracts |
| Dev-env OpenSpec | `dev-env/openspec/specs/pstack-gascity-pack/spec.md` | Durable requirements, scenarios, architecture, ADR, and tasks |

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

## Evidence classes

- **Static:** TOML/YAML parse, source parity, formula metadata, schema references, provider-name absence.
- **Metadata:** disposable graph cooking with a temporary Beads/file backend; validates node order and metadata only.
- **Runtime:** provider and live Gas City execution; not performed by pack-local verification.
- **Unavailable:** optional pack, provider, or live city not present; reported with a reason.

## Delivery boundary

This checkout is prepared for review. Commit, push, pack publication, live import, canonical city mutation, Formula sling, and live Beads mutation remain independent operations.
