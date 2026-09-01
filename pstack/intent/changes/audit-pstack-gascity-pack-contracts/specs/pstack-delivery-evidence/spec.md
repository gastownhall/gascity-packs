## ADDED Requirements

### Requirement: Formula requirement metadata is checked in delivery

Feature: pstack-delivery-evidence

Rule: Compiler requirements fail in the focused suite

The PStack pack test suite MUST check that every discovered PStack formula
contains the supported formula compiler requirement before the live matrix is
used as delivery evidence.

#### Scenario: Missing formula requirement fails the focused check

- **GIVEN** a PStack formula omits `requires.formula_compiler`
- **WHEN** the pack conformance test runs
- **THEN** it fails before accepting the delivery contract
