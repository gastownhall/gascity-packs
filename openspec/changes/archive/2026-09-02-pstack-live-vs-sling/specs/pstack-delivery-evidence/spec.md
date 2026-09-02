## MODIFIED Requirements

### Requirement: PStack traceability references durable truth

`pstack/TRACEABILITY.md` MUST point to the durable canonical specification `openspec/specs/pstack-gascity-pack/spec.md` and MUST NOT point to a removed change directory as the current contract. Its evidence classes MUST continue to distinguish static, metadata, runtime, and unavailable claims. It MUST name `docs/pstack-program-plan.md` as the live program. That plan's Arm `git show origin/main:` list MUST name files that exist in this repository's origin/main. Focused pack tests MUST require the live Durable Gherkin AND that TRACEABILITY does not name another project as the Gherkin owner. A former-checkout token grep MUST NOT substitute for that AND. It MUST say disposable live-city import is exercised when `GC_TEST_BIN` is set. It MUST say formula sling of `pstack-poteto-mode` and `pstack-build` remains unproven. Pack tests MUST lock both sentences.

#### Scenario: Traceability path is stable

- **GIVEN** a fresh checkout of the pack repository
- **WHEN** a reader follows the durable PStack specification reference in `pstack/TRACEABILITY.md`
- **THEN** the reference identifies `openspec/specs/pstack-gascity-pack/spec.md`
- **AND** it does not present a historical change directory as the current contract

#### Scenario: Live program is the recursive graph

- **GIVEN** `pstack/TRACEABILITY.md` and `docs/pstack-program-plan.md`
- **WHEN** an operator follows the live program
- **THEN** TRACEABILITY names `docs/pstack-program-plan.md`
- **AND** that plan names `pr-pstack-land-honesty` then `pr-pstack-panel-stamp`

#### Scenario: Arm list is re-runnable on trunk

- **GIVEN** `docs/pstack-program-plan.md`
- **WHEN** an operator runs each `git show origin/main:` box in Arm the program
- **THEN** every path exists in this repository's origin/main
- **AND** those boxes do not require plugin `skills/` on origin/main

#### Scenario: Tests fail closed on a foreign Gherkin owner

- **GIVEN** `pstack/tests/test_pstack_pack.py` and `openspec/specs/pstack-gascity-pack/spec.md`
- **WHEN** the focused pack tests run
- **THEN** they require TRACEABILITY to name `openspec/specs/pstack-gascity-pack/spec.md`
- **AND** they require the live spec AND `it does not name another project as the Gherkin owner`
- **AND** they fail if TRACEABILITY uses `gherkin owner`

#### Scenario: TRACEABILITY splits live-city import from formula sling

- **GIVEN** `pstack/TRACEABILITY.md` and `pstack/tests/test_pstack_pack.py`
- **WHEN** a reader follows the OpenSpec payload note
- **AND** the focused pack tests run
- **THEN** TRACEABILITY says disposable live-city import is exercised when `GC_TEST_BIN` is set
- **AND** TRACEABILITY says formula sling of `pstack-poteto-mode` and `pstack-build` remains unproven
- **AND** TRACEABILITY does not say `Live city sling remains unproven`
- **AND** the tests fail if either required sentence is missing
