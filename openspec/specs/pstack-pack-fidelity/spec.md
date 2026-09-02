# pstack-pack-fidelity Specification

## Purpose

Keep the PStack pack's vendored source, runtime adaptations, formula metadata,
and shared evidence validator aligned with the supported Gas City contract.

## Requirements

### Requirement: Shared artifact validation remains portable

The shared build-artifact validator invoked through bare `python3` MUST retain the
runtime compatibility of the existing validator. A compatibility-preserving
standard-library implementation MUST be used for ordered-section validation;
the gate MUST NOT require Python 3.10-only APIs unless the repository declares
that floor.

#### Scenario: Ordered sections validate on the supported Python runtime

- **GIVEN** an artifact body whose required sections are in the declared order
- **WHEN** the shared validator checks section order
- **THEN** it accepts the body without importing a newer-than-supported standard-library API
- **AND** an out-of-order body still fails with the existing section-order diagnostic

### Requirement: Vendored source and runtime boundaries remain explicit

Feature: pstack-pack-fidelity

Rule: The pack pin is a reviewed Cursor snapshot, not latest main

The PStack pack MUST record the reviewed Cursor plugins commit in
`vendor/pstack/upstream.toml`, keep the vendored `pstack/` listed paths exact
at that revision, include Cursor plugin `agents/`, omit `docs/` and
`automations/`, and keep Gas City mapping outside the vendor tree.
`vendor/pstack/upstream.toml` MUST set `source` to
`https://github.com/cursor/plugins`, `path` to `pstack`, and `commit` to
`6fecddba65801f9b9c08b8b328d998ee5b09d290`. The pack MUST NOT pin
`tommy-ca/pstack`. Pack-owned formulas, assets, and agents MUST NOT prescribe
`scripts/watch-pr/watch-pr` or `scripts/orch/orch.ts`. Vendored Cursor
playbooks MAY contain those paths as upstream text. TRACEABILITY MUST record
later Cursor `main` differences as reviewed-but-not-vendored drift and MUST
NOT name a moving maintained SHA as the durable pin.

#### Scenario: Vendor refresh preserves host-boundary behavior

- **GIVEN** the pack's recorded PStack source revision is refreshed
- **WHEN** the source and runtime fidelity checks run
- **THEN** the recorded revision and vendored paths agree
- **AND** pack-owned formulas, assets, and agents contain no `scripts/watch-pr` or `scripts/orch/orch.ts` live path
- **AND** a vendored Cursor playbook that names those paths does not fail the host-boundary check
- **AND** `vendor/pstack/agents/` contains the Cursor plugin agent files
- **AND** `vendor/pstack/docs` and `vendor/pstack/automations` do not exist
- **AND** Gas City mapping remains outside `vendor/pstack/`

#### Scenario: Post-pin source changes remain reviewable

- **GIVEN** the maintained PStack checkout is newer than the recorded vendor pin
- **WHEN** source traceability is reviewed
- **THEN** the pack keeps the explicit reviewed revision in `upstream.toml`
- **AND** later Cursor `main` differences are identified as reviewed-but-not-vendored drift, including `README.md` and `skills/poteto-mode/playbooks/`
- **AND** TRACEABILITY names drifted path classes rather than a moving maintained SHA
- **AND** the pack does not silently copy later source files into the vendor tree

### Requirement: PStack formulas use the canonical compiler requirement

Every PStack formula MUST declare the supported formula compiler requirement
`formula_compiler >= 2.0.0` and MUST NOT retain the deprecated
`contract = "graph.v2"` field. The pack's live doctor contract MUST therefore
expect no PStack-specific `formula-requirements` finding after installation.

#### Scenario: Formula metadata is accepted by Gas City

- **GIVEN** every formula discovered under `pstack/formulas/`
- **WHEN** the pack is linted and imported into a disposable city
- **THEN** each formula declares the compiler requirement and omits the deprecated contract
- **AND** the PStack-specific doctor delta is empty
- **AND** the canary control still proves that doctor findings are observable

### Requirement: Decision artifacts support explicit no-removal outcomes

The immutable `pstack.decision.v1` schema MUST accept
`status: no_removal_opportunity` for a trivial subtraction assessment, while
retaining the required subtraction and rationale fields.

#### Scenario: Trivial subtraction is recorded instead of skipped

- **GIVEN** a PStack build has no removable complexity before construction
- **WHEN** the subtraction stage writes its decision artifact
- **THEN** it may use `status: no_removal_opportunity`
- **AND** the artifact still requires a non-empty `subtraction` value and rationale
- **AND** the shared validator accepts the artifact

### Requirement: Pack tests enforce parity, ordering, and evidence

The repository MUST add PStack to the existing derived-pack compatibility registry
alongside `compound-engineering`, `superpowers`, `bmad`, and `gstack`
and MUST add focused tests for exact 21-principle parity, manifest/enforcement
coverage, source traceability, formula anchor ordering, selector compatibility,
standard schemas, providerless routes, principle ordering, revision-bound
verification, formula compiler requirements, the explicit no-removal status,
pack-owned host-boundary strings, unconsumed graph-operator metadata,
reviewed-but-not-vendored source drift, and the absence of pack-local OpenSpec
payloads. Tests MUST fail closed when these contracts regress. A
`restart_token` field is schema data, not a continuation-semantics suite.

#### Scenario: Fidelity regressions fail in the focused pack suite

- **GIVEN** a formula retains a deprecated graph contract or omits its compiler requirement, a decision schema rejects the documented no-removal status, or a pack-owned asset restores a forbidden local path
- **WHEN** `pstack/tests/test_pstack_pack.py` runs
- **THEN** the suite identifies the exact violated contract and fails
- **AND** unrelated provider, publication, registry, or canonical-city actions are not required for the check

### Requirement: PStack schemas have a rerunnable validator

Feature: pstack-pack-fidelity

Rule: Schema YAML is checked by a pack script, not by hand

The pack MUST ship `pstack/scripts/validate_pstack_schemas.py`. That script
MUST load every `pstack/schemas/*.yaml` file, require `schema_id` `pstack.<stem>`,
`producer.attempt` in `required_front_matter`, the shared coverage-status
vocabulary, and formula `pstack.artifact_schema` values that exist. The
script MUST reuse Gas City `validate_schema_definition` when that loader is
present. The pack MUST NOT require pydantic for schema inventory.

#### Scenario: Schema validator fails closed

- **GIVEN** a schema YAML missing `producer.attempt` or an unknown `pstack.artifact_schema` on a formula
- **WHEN** `python pstack/scripts/validate_pstack_schemas.py` runs
- **THEN** it exits nonzero
- **AND** `pstack/tests/test_pstack_pack.py` fails the schema inventory test
