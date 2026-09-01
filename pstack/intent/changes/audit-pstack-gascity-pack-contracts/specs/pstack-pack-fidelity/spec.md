## MODIFIED Requirements

### Requirement: Vendored source and runtime boundaries remain explicit

Feature: pstack-pack-fidelity

Rule: The pack pin is a reviewed snapshot, not latest main

The PStack pack MUST record the reviewed source revision in
`vendor/pstack/upstream.toml`, keep the vendored source exact at that revision,
and keep runtime adaptations outside the vendor tree. Vendored host-boundary
playbooks MUST NOT reintroduce the repository-local watcher or durable
orchestration store prohibited by the maintained host contract. TRACEABILITY
MUST record later maintained-source documentation or adapter-reference
differences as reviewed-but-not-vendored drift and MUST NOT name a moving
maintained SHA as the durable pin.

#### Scenario: Vendor refresh preserves host-boundary behavior

- **GIVEN** the pack's recorded PStack source revision is refreshed
- **WHEN** the source and runtime fidelity checks run
- **THEN** the recorded revision and vendored paths agree
- **AND** the vendored babysit and orchestrate playbooks contain no `scripts/watch-pr/watch-pr` or `scripts/orch/orch.ts` live path
- **AND** runtime-adapted assets remain outside `vendor/pstack/`

#### Scenario: Post-pin source changes remain reviewable

- **GIVEN** the maintained PStack checkout is newer than the recorded vendor pin
- **WHEN** source traceability is reviewed
- **THEN** the pack keeps the explicit reviewed revision in `upstream.toml`
- **AND** later documentation or adapter-reference differences are identified as reviewed-but-not-vendored drift, including `README.md`, `docs/guide/06-verify-and-ship.md`, `docs/guide/13-grok-natives.md`, `skills/poteto-mode/references/codex-tools.md`, and `skills/poteto-mode/references/github-pr-fallback.md`
- **AND** TRACEABILITY names drifted path classes rather than a moving maintained SHA
- **AND** the pack does not silently copy later source files into the vendor tree

### Requirement: Pack tests enforce parity, ordering, and evidence

The repository MUST add PStack to the existing derived-pack compatibility registry
and MUST add focused tests for exact 21-principle parity, manifest/enforcement
coverage, source traceability, formula anchor ordering, selector compatibility,
standard schemas, providerless routes, principle ordering, revision-bound
verification, formula compiler requirements, the explicit no-removal status,
vendored host-boundary strings, unconsumed graph-operator metadata, and
reviewed-but-not-vendored source drift. Tests MUST fail closed when these
contracts regress. A `restart_token` field is schema data, not a
continuation-semantics suite.

#### Scenario: Fidelity regressions fail in the focused pack suite

- **GIVEN** a formula retains a deprecated graph contract or omits its compiler requirement, a decision schema rejects the documented no-removal status, or a vendored playbook restores a forbidden local path
- **WHEN** `pstack/tests/test_pstack_pack.py` runs
- **THEN** the suite identifies the exact violated contract and fails
- **AND** unrelated provider, publication, registry, or canonical-city actions are not required for the check
