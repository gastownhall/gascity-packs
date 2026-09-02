## ADDED Requirements

### Requirement: Implementation convoy inherits do-work worktree assets

Feature: pstack-gascity-pack

Rule: pstack-work must not blank the inherited source-anchor contract

`pstack-work` MUST extend `do-work`. It MUST default `implementation_target`
to `pstack.implementation-worker`. It MUST NOT replace `prepare-worktree` or
`close-source-anchor` with pack-local stub `description_file` paths.

#### Scenario: pstack-work keeps do-work worktree steps

- **GIVEN** `pstack/formulas/pstack-work.formula.toml`
- **WHEN** the focused pack tests run
- **THEN** the formula extends `do-work`
- **AND** it has no pack-local `prepare-worktree` or `close-source-anchor` step override
- **AND** `implementation_target` defaults to `pstack.implementation-worker`

## MODIFIED Requirements

### Requirement: PStack methods and programs are composable Gas City formulas

Feature: pstack-gascity-pack

Rule: Method formulas stay Gas City-owned and do not invent a second scheduler

The pack MUST represent `how`, `why`, `architect`, `swarm`, `arena`, and
`interrogate` as standalone or composable Gas City formulas. Those formulas MAY
annotate intended fanout, fanin, gate, or selector behavior with
`gc.graph_operator` or `pstack.graph_operator` metadata. This checkout MUST NOT
treat those keys as an executed child-graph primitive. This checkout MUST NOT
stamp `gc.provider_panel` until Gas City consumes that key. After
that consumer exists, `pstack-arena` and `pstack-interrogate` MUST delegate
N-model children to a city provider panel and MUST declare isolated
`{child_id}` artifact paths. Feature, refactor,
bug-fix, perf, prototype, investigation, hillclimb, runtime-forensics,
trace-forensics, eval, authoring-a-skill, session-pickup, multi-phase-plan,
visual-parity, autonomous-run, orchestrate, autopilot, babysit, and shipping
formulas MUST compose the standard build or method formulas rather than
duplicate lifecycle infrastructure. `opening-a-pr`, `pause-safely`, and
`worktree-cleanup` MUST remain unsupported as sling formulas. Analysis
formulas MUST NOT be forced through implementation/publish anchors. Method
formulas MUST identify runtime behavior through their formula identity and
`gc.run_target`; they MUST NOT carry an unconsumed `pstack.skill` selector that
names a runtime skill path. `pstack-poteto-mode` MUST classify a request into
a mapped formula or an unsupported playbook and MUST write `pstack.route.v1`.
It MUST NOT expand into the selected formula and MUST NOT set
`gc.graph_operator`. Pack-owned formulas, assets, and agents MUST NOT name
provider ids. `pstack-interrogate` judgment MUST set
`gc.build.artifact_schema` to `gc.build.review.v1`, MUST set
`gc.build.artifact_path_keys`, and MUST run the shared build-artifact
validator.

#### Scenario: Poteto-mode router classifies without auto-sling

- **GIVEN** the resolved `pstack-poteto-mode` formula and `pstack/mappings/playbooks.toml`
- **WHEN** classify and write run
- **THEN** the artifact schema is `pstack.route.v1`
- **AND** a mapped playbook records `status: routed` and a formula that exists
- **AND** `opening-a-pr` records `status: unsupported`
- **AND** no step sets `gc.graph_operator`

#### Scenario: Babysit escalation is a checked evidence producer

- **GIVEN** the resolved `pstack-babysit` formula
- **WHEN** its `escalate` step is inspected
- **THEN** the step has a direct `description_file` and `gc.run_target` metadata
- **AND** it declares `pstack.program-status.v1` with the `pstack.artifact_path` output binding
- **AND** its check runs the shared build-artifact validator
- **AND** `finalize` depends on the escalation result

#### Scenario: Swarm uses durable fanout

- **GIVEN** a swarm request with independent work units
- **WHEN** `pstack-swarm` is inspected as a Gas City formula
- **THEN** it has sequential `frame`, `fanout`, and `fanin` steps
- **AND** the fanout and fanin steps may set `gc.graph_operator` metadata
- **AND** this checkout has no Gas City consumer that expands those keys into child work
- **AND** the formula does not invoke a provider-native task engine or create a second scheduler

#### Scenario: Arena compares genuinely distinct candidates

- **GIVEN** a novel architectural or experience-sensitive decision
- **WHEN** `pstack-arena` is inspected as a Gas City formula in this checkout
- **THEN** `trigger`, `candidates`, `judge`, and `verify` steps run in order
- **AND** candidates write `pstack.arena-candidate.v1` at the declared path
- **AND** judge writes `pstack.arena-synthesis.v1`
- **AND** verify writes `pstack.verification.v1`
- **AND** the formula does not expand multiple candidate graph children in this checkout
- **AND** the formula does not stamp `gc.provider_panel`

#### Scenario: Interrogate selects review lanes

- **GIVEN** a review intent with several possible dimensions
- **WHEN** `pstack-interrogate` is inspected as a Gas City formula in this checkout
- **THEN** `select`, `review`, and `judgment` steps run in order
- **AND** `select` records applicable review dimensions
- **AND** review may set `gc.graph_operator` as annotation
- **AND** judgment produces a review artifact
- **AND** judgment sets `gc.build.artifact_schema` to `gc.build.review.v1`
- **AND** judgment sets `gc.build.artifact_path_keys`
- **AND** judgment runs the shared build-artifact validator
- **AND** independent reviewer lanes are not expanded as separate graph children in this checkout
- **AND** the formula does not stamp `gc.provider_panel`
- **AND** after a panel consumer exists, the panel fans the `review` node only and MUST NOT replace `select` with provider ids

#### Scenario: Graph-operator metadata stays uninterpreted

- **GIVEN** `pstack-swarm`, `pstack-arena`, or `pstack-interrogate`
- **WHEN** pack tests and TRACEABILITY are inspected
- **THEN** those formulas still declare `gc.graph_operator` or `pstack.graph_operator`
- **AND** TRACEABILITY records that this checkout has no Gas City consumer for those fields
- **AND** the formulas do not dispatch through a provider-native durable API
- **AND** TRACEABILITY names swarm as work-unit annotation
- **AND** TRACEABILITY names a city provider panel as the arena and interrogate N-model target
- **AND** TRACEABILITY records that this checkout has no compiler consumer for `gc.provider_panel`

#### Scenario: Pack docs describe city provider panels without stamping them

- **GIVEN** `pstack/DESIGN.md`, `pstack/ARCHITECTURE.md`, and `pstack/REQUIREMENTS.md`
- **WHEN** a city operator reads how N-model fanout will work
- **THEN** those files name `[[provider_panels]]` and `gc.provider_panel`
- **AND** they forbid pack-owned provider id strings
- **AND** they forbid stamping `gc.provider_panel` before a Gas City consumer exists
- **AND** `pstack-arena.formula.toml` still omits `gc.provider_panel`

#### Scenario: Analysis remains read-mostly

- **GIVEN** a `how`, `why`, or investigation request
- **WHEN** its formula executes
- **THEN** it gathers evidence, runs a bounded read-only sequence, and synthesizes findings
- **AND** the formula does not select an unconsumed runtime skill through `pstack.skill`
