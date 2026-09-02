## MODIFIED Requirements

### Requirement: PStack traceability references durable truth

`pstack/TRACEABILITY.md` MUST point to the durable canonical specification `openspec/specs/pstack-gascity-pack/spec.md` and MUST NOT point to a removed change directory as the current contract. Its evidence classes MUST continue to distinguish static, metadata, runtime, and unavailable claims. It MUST name `docs/pstack-program-plan.md` as the live program.

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
