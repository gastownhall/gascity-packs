## ADDED Requirements

### Requirement: Remaining program units stay host sling then compiler then panel stamp

Feature: pstack-delivery-evidence

Rule: Isolation on PR 385 does not authorize restamp or panel stamp

The live program MUST name host sling of `pstack-poteto-mode` then
`pstack-build` as the next operator unit after `pr-pstack-land-honesty` is on
PR 385. That unit MUST NOT be a GitHub PR. Restamp of registry `0.1.0` MUST
wait on those sling receipts. `pstack/TRACEABILITY.md` MUST name both formulas
on the restamp gate. The program MUST say `pr-pstack-panel-stamp` must not
start on Gherkin alone. Pack tests MUST fail if any
`pstack/formulas/*.formula.toml` contains `gc.provider_panel` or
`gc.child_artifact_path_template`. Pack tests MUST fail if `gascity/` contains
`provider_panel`. Presence of `openspec/specs/gascity-provider-panel/spec.md`
MUST NOT authorize a formula stamp.

#### Scenario: Host sling is the next operator unit

- **GIVEN** `docs/pstack-program-plan.md`
- **WHEN** an operator follows the spawn graph after isolation is on PR 385
- **THEN** the next unit names host sling of `pstack-poteto-mode` and `pstack-build`
- **AND** that unit is not a GitHub PR
- **AND** restamp of `registry.toml` 0.1.0 waits on sling receipts

#### Scenario: TRACEABILITY names both sling formulas on the restamp gate

- **GIVEN** `pstack/TRACEABILITY.md`
- **WHEN** a reader follows the delivery boundary
- **THEN** it forbids restamping `commit` or `hash` without a host sling
- **AND** that sentence names `pstack-poteto-mode` and `pstack-build`

#### Scenario: Panel stamp does not start on Gherkin alone

- **GIVEN** `docs/pstack-program-plan.md` and `openspec/specs/gascity-provider-panel/spec.md`
- **WHEN** an operator considers `pr-pstack-panel-stamp`
- **THEN** the program says the compiler is outside this packs tree
- **AND** it says `pr-pstack-panel-stamp` must not start on Gherkin alone
- **AND** pack formulas still omit `gc.provider_panel`

#### Scenario: Tests fail closed on a premature panel stamp

- **GIVEN** `pstack/tests/test_pstack_pack.py`
- **WHEN** the focused pack tests run
- **THEN** every `pstack/formulas/*.formula.toml` omits `gc.provider_panel`
- **AND** every such file omits `gc.child_artifact_path_template`
- **AND** `gascity/` has no `provider_panel` hit
