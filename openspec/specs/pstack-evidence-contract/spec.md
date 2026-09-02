# pstack-evidence-contract Specification

## Purpose

Define canonical principle-enforcement declarations and fail-closed evidence validation for the PStack pack.

## Requirements

### Requirement: Required artifact declarations fail closed

The shared build-artifact validator MUST treat an explicitly present
`required_fields` schema declaration as a non-empty list of non-empty field
paths. For every declared required field, the artifact MUST provide a
non-empty scalar or container value. The validator MUST retain the
execution-metadata guard for forbidden owner/persona/role leaves in
`required_front_matter`; namespaced domain fields in `required_fields` remain
domain data and are not subject to that execution-metadata blacklist.

#### Scenario: Empty required-field schema declarations are rejected

- **GIVEN** a custom schema that explicitly declares `required_fields: []`, a non-list value, or a list containing a blank/non-string field path
- **WHEN** the schema is loaded by the shared validator
- **THEN** validation fails with a schema-definition error

#### Scenario: Empty required-field values are rejected

- **GIVEN** a valid schema with a required field
- **WHEN** an artifact supplies that field as whitespace, an empty list, or an empty mapping
- **THEN** validation fails with a required-field non-empty error

#### Scenario: Domain owner fields remain valid

- **GIVEN** a namespaced PStack schema that requires the domain field `owner`
- **WHEN** the artifact supplies a non-empty owner value
- **THEN** the shared validator accepts the field
- **AND** the execution-metadata blacklist still rejects a forbidden `required_front_matter` leaf such as `producer.role`

### Requirement: Decision artifacts record explicit subtraction outcomes

The PStack decision artifact contract MUST allow a trivial subtraction assessment
to use `status: no_removal_opportunity`. The artifact MUST still contain a
non-empty `subtraction` field and a non-empty `rationale`, and the shared
validator MUST fail closed for missing or empty values.

#### Scenario: No-removal decision validates

- **GIVEN** a valid `pstack.decision.v1` artifact whose subtraction found no removable complexity
- **WHEN** the shared validator checks the artifact
- **THEN** `status: no_removal_opportunity` is accepted
- **AND** non-empty `subtraction` and `rationale` values are required

#### Scenario: Invalid no-removal decision fails closed

- **GIVEN** a `pstack.decision.v1` artifact with the no-removal status and an empty subtraction or rationale
- **WHEN** the shared validator checks the artifact
- **THEN** validation fails with the required-field diagnostic

### Requirement: Validator portability is preserved

The shared artifact validator MUST remain executable by the repository's bare
`python3` gate without introducing a newer-only standard-library import for
existing behavior. Ordered required sections MUST retain their current success
and failure semantics on the supported Python runtime.

#### Scenario: Section order keeps its existing behavior

- **GIVEN** required sections appear in declaration order
- **WHEN** the validator checks their order
- **THEN** validation succeeds
- **AND** a reordered section produces the existing order diagnostic
