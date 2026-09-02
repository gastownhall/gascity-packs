## MODIFIED Requirements

### Requirement: Apply change name follows the source directory

Feature: pstack-gascity-pack

Rule: No hardcoded default change name

`pstack/scripts/apply_intent_change.py` MUST NOT define `DEFAULT_CHANGE`.
When `--change` is omitted, the change name MUST be the `--source`
directory name with a leading `YYYY-MM-DD-` prefix removed when present.
When `--change` is passed, that value MUST win.

#### Scenario: Dated archive validates without --change

- **GIVEN** `--source` is `openspec/changes/archive/2026-09-02-pstack-mapping-gaps`
- **AND** `--change` is omitted
- **WHEN** validate-only runs
- **THEN** the change name is `pstack-mapping-gaps`
- **AND** OpenSpec strict validate uses that name

#### Scenario: Explicit --change wins

- **GIVEN** `--source` is `openspec/changes/archive/2026-09-02-pstack-mapping-gaps`
- **AND** `--change` is `pstack-gherkin-restamp`
- **WHEN** validate-only runs
- **THEN** the change name is `pstack-gherkin-restamp`
