## MODIFIED Requirements

### Requirement: PStack build uses standard artifacts and explicit methodology gates

`pstack-build` MUST use `gc.build.requirements.v1`,
`gc.build.plan.v1`, `gc.build.decomposition.v1`,
`gc.build.implementation-summary.v1`, `gc.build.review.v1`, and
`gc.build.final-report.v1` for ordinary lifecycle artifacts. PStack-specific
semantic objects MUST use namespaced schemas only when no `gc.build.*` schema
represents them. The build graph MUST support `subtract-assessment`,
`lever-decision`, and principle-selection behavior as explicit gated steps or
graph metadata without replacing base anchors. A trivial subtraction
assessment MUST be representable by `pstack.decision.v1` with
`status: no_removal_opportunity` and a reason. Selector formulas MUST follow
sibling methodology packs: `pstack-planning` overrides pack-local assets and
`pstack.*` run targets, and `pstack-decomposition` declares `lever-decision`
before `decompose`.

#### Scenario: Build method compiles from standard selectors

- **GIVEN** the `pstack-build` selector defaults
- **WHEN** the formula is shown or cooked
- **THEN** planning, decomposition, implementation, item, review, and fix-loop selectors resolve to PStack formulas
- **AND** every selector preserves the base variable and artifact contracts
- **AND** every role route is providerless and resolved by Gas City deployment configuration
- **AND** `pstack-planning` overrides requirements, plan, and plan-review with pack-local assets and `pstack.*` run targets
- **AND** `pstack-decomposition` declares `lever-decision` before `decompose`

#### Scenario: Subtraction precedes construction

- **GIVEN** a refactor, rewrite, migration, or architecture-changing build
- **WHEN** PStack planning evaluates the work
- **THEN** the graph evaluates removable complexity before adding new structure
- **AND** identified removal is sequenced before construction unless the intermediate state would be unrecoverable
- **AND** a trivial case records `status: no_removal_opportunity` with a reason instead of silently skipping the stage

#### Scenario: Lever decision precedes repetitive fanout

- **GIVEN** a `pstack-build` or `pstack-decomposition` formula
- **WHEN** decomposition is inspected
- **THEN** it emits `pstack.lever-decision.v1`
- **AND** `decompose` needs `lever-decision`
- **AND** a selected lever is recorded before task-bead fanout

### Requirement: PStack methods and programs are composable Gas City formulas

Feature: pstack-gascity-pack

Rule: Method formulas stay Gas City-owned and do not invent a second scheduler

The pack MUST represent `how`, `why`, `architect`, `swarm`, `arena`, and
`interrogate` as standalone or composable Gas City formulas. Those formulas MAY
annotate intended fanout, fanin, gate, or selector behavior with
`gc.graph_operator` or `pstack.graph_operator` metadata. This checkout MUST NOT
treat those keys as an executed child-graph primitive. Feature, refactor,
bug-fix, perf, prototype, investigation, autonomous-run, orchestrate,
autopilot, babysit, and shipping formulas MUST compose the standard build or
method formulas rather than duplicate lifecycle infrastructure. Analysis
formulas MUST NOT be forced through implementation/publish anchors. Method
formulas MUST identify runtime behavior through their formula identity and
`gc.run_target`; they MUST NOT carry an unconsumed `pstack.skill` selector that
names a runtime skill path.

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
- **WHEN** `pstack-arena` is inspected as a Gas City formula
- **THEN** `trigger`, `candidates`, `judge`, and `verify` steps run in order
- **AND** candidates write `pstack.arena-candidate.v1` at the declared path
- **AND** judge writes `pstack.arena-synthesis.v1`
- **AND** verify writes `pstack.verification.v1`
- **AND** the formula does not expand multiple candidate graph children in this checkout

#### Scenario: Interrogate selects review lanes

- **GIVEN** a review intent with several possible dimensions
- **WHEN** `pstack-interrogate` is inspected as a Gas City formula
- **THEN** `select`, `review`, and `judgment` steps run in order
- **AND** review may set `gc.graph_operator` as annotation
- **AND** judgment produces a review artifact
- **AND** independent reviewer lanes are not expanded as separate graph children in this checkout

#### Scenario: Graph-operator metadata stays uninterpreted

- **GIVEN** `pstack-swarm`, `pstack-arena`, or `pstack-interrogate`
- **WHEN** pack tests and TRACEABILITY are inspected
- **THEN** those formulas still declare `gc.graph_operator` or `pstack.graph_operator`
- **AND** TRACEABILITY records that this checkout has no Gas City consumer for those fields
- **AND** the formulas do not dispatch through a provider-native durable API

#### Scenario: Analysis remains read-mostly

- **GIVEN** a `how`, `why`, or investigation request
- **WHEN** its formula executes
- **THEN** it gathers evidence, runs a bounded read-only sequence, and synthesizes findings
- **AND** the formula does not select an unconsumed runtime skill through `pstack.skill`

### Requirement: Optional pack composition remains decoupled

Feature: pstack-gascity-pack

Rule: Optional packs never block core loading

Core PStack MUST run with only Gas City plus its own pack. Optional methodology
composition listed in `pstack/mappings/optional-packs.toml` MUST be
`compound-engineering`, `superpowers`, `bmad`, and `gstack`, each
`required = false`. Action integrations such as PR Pipeline, GitHub, Slack, and
Gastown MAY be composed at city scope when those packs are installed. PStack
MUST reuse compatible existing capabilities and MUST NOT reimplement their
event intake, session search, project-lead hierarchy, publication mechanics, or
stuck-worker runtime.

#### Scenario: Optional capability is absent

- **GIVEN** an optional methodology pack listed in `optional-packs.toml` is not installed
- **WHEN** core PStack formulas are loaded
- **THEN** those formulas remain loadable
- **AND** a missing optional pack does not block pack import

#### Scenario: External action remains gated

- **GIVEN** a workflow reaches GitHub, Slack, branch publication, or PR creation
- **WHEN** the external action is selected
- **THEN** the existing integration or publish gate owns the action
- **AND** PStack provides methodology evidence and eligibility, not a duplicate webhook/client runtime

### Requirement: Pack tests enforce parity, ordering, and evidence

The repository MUST add PStack to the existing derived-pack compatibility
registry and MUST add focused tests for exact 21-principle parity,
manifest/enforcement coverage, source traceability, formula anchor ordering,
selector compatibility, standard schemas, providerless routes, principle
ordering, revision-bound verification, formula compiler requirements, the
explicit no-removal status, vendored host-boundary strings, unconsumed
graph-operator metadata, and reviewed-but-not-vendored source drift. Tests MUST
fail closed when these contracts regress. Metadata evidence MUST be inspectable
formula TOML plus disposable live-city formula and agent listing. Tests MUST
NOT require a separate graph-cook script. A `restart_token` field on
`pstack.program-status.v1` is schema data, not a continuation-semantics suite.

#### Scenario: Derived-pack suite includes PStack

- **GIVEN** the existing `gascity/tests/test_derived_pack_compatibility.py` registry
- **WHEN** the Gas City pack test suite runs
- **THEN** `pstack` is checked alongside the existing methodology packs
- **AND** `pstack-build` is tested for `build-base` inheritance, standard metadata, selector defaults, drain policy, providerless routes, claim protocol, and pack-local requirements

#### Scenario: Principle parity fails closed

- **GIVEN** a missing principle skill, manifest entry, enforcement declaration, or test fixture
- **WHEN** the PStack conformance suite runs
- **THEN** the suite fails with the missing principle and expected path
- **AND** no partial nine-principle or subset result is accepted as PStack compatibility

#### Scenario: Metadata cook proves graph shape only

- **GIVEN** the focused pack tests and the disposable live-city matrix
- **WHEN** PStack formulas are parsed and listed
- **THEN** required `gc.run_target`, schema, variable, dependency, and check metadata are inspectable in formula files
- **AND** live-city listing does not claim provider execution, Beads mutation, merge, publication, or runtime success

#### Scenario: Pack conformance fails closed

- **GIVEN** a formula retains a deprecated graph contract or omits its compiler requirement, a decision schema rejects the documented no-removal status, or a vendored playbook restores a forbidden local path
- **WHEN** the focused PStack and shared Gas City tests run
- **THEN** they fail with the violated contract
- **AND** no partial compatibility result is accepted

### Requirement: Upstream pstack corpus is exact and traceable

Discipline source is official Cursor pstack at
`https://github.com/cursor/plugins/tree/main/pstack` tree
`6fecddba65801f9b9c08b8b328d998ee5b09d290`. Pack shape follows gascity-packs
methodology packs (`bmad`, `superpowers`, `gstack`, `compound-engineering`)
extending Gas City virtual contracts. The pack MUST vendor a reviewed runtime
corpus under `vendor/pstack/` at the immutable pin in
`vendor/pstack/upstream.toml`. That pin MAY be a host-adapted tree such as
`tommy-ca/pstack` so babysit and orchestrate do not prescribe
`scripts/watch-pr/watch-pr` or `scripts/orch/orch.ts`. Runtime-specific Gas City
prompts MUST live outside the vendored corpus. Focused tests MUST pin that
revision, prove runtime `skills/` matches `vendor/pstack/skills/`, and grep
host-boundary playbooks. Tests MUST NOT require a `git archive` of Cursor
`main`.

`pstack/ARCHITECTURE.md` MUST record the building-block map from Cursor
playbooks and principles onto Gas City formulas and primitives.

#### Scenario: Vendor parity is checked

- **GIVEN** the recorded pstack upstream revision
- **WHEN** the focused pack tests run
- **THEN** `vendor/pstack/upstream.toml` records that revision
- **AND** all 21 canonical principle skill directories are present under runtime `skills/`
- **AND** runtime `skills/` matches `vendor/pstack/skills/` byte-for-byte
- **AND** the vendored host-boundary playbooks contain no prohibited local watcher or store path

#### Scenario: Runtime prompts do not mutate source material

- **GIVEN** a Gas City formula or role prompt that adapts pstack behavior
- **WHEN** the prompt is resolved
- **THEN** it references vendored methodology or a pack-owned mapping
- **AND** it does not rewrite the vendored file or dispatch through a provider-native durable API

#### Scenario: Discipline source stays Cursor pstack

- **GIVEN** `pstack/TRACEABILITY.md` and `pstack/ARCHITECTURE.md`
- **WHEN** a reader follows the discipline source
- **THEN** TRACEABILITY names `https://github.com/cursor/plugins/tree/main/pstack` and tree `6fecddba65801f9b9c08b8b328d998ee5b09d290`
- **AND** `vendor/pstack/upstream.toml` still records the reviewed runtime pin
- **AND** ARCHITECTURE names `build-base` and sibling methodology packs as the packing reference

### Requirement: All 21 principles have first-class enforcement

The pack MUST provide one first-class leaf skill and one machine-readable
manifest entry for each canonical principle:
`laziness-protocol`, `foundational-thinking`,
`redesign-from-first-principles`, `subtract-before-you-add`,
`minimize-reader-load`, `outcome-oriented-execution`, `experience-first`,
`exhaust-the-design-space`, `build-the-lever`, `model-the-domain`,
`boundary-discipline`, `type-system-discipline`, `make-operations-idempotent`,
`migrate-callers-then-delete-legacy-apis`,
`separate-before-serializing-shared-state`, `prove-it-works`,
`fix-root-causes`, `sequence-verifiable-units`, `guard-the-context-window`,
`never-block-on-the-human`, and `encode-lessons-in-structure`.
Every manifest entry MUST declare triggers, applicable workflows, one or more
enforcement values from the canonical set `artifact`, `check`, `expansion`,
`graph-invariant`, or `review`, and applicable required artifacts.
Applicable principles MUST be selected per role/formula rather than loading
every body into every worker. `pstack-source-binding` MAY record a translation
artifact. The catalog MUST NOT require one committed source-binding row per
principle ID.

#### Scenario: Principle catalog is complete

- **GIVEN** the pack principle manifest
- **WHEN** the catalog parity test runs
- **THEN** exactly the 21 canonical principle IDs are represented
- **AND** every ID resolves to one skill directory and one manifest row
- **AND** no duplicate or untracked principle is silently accepted

#### Scenario: Principle enforcement is declared with one vocabulary

- **GIVEN** any principle manifest entry
- **WHEN** the enforcement coverage test runs
- **THEN** its enforcement set contains one or more values from `artifact`, `check`, `expansion`, `graph-invariant`, or `review`
- **AND** the mapping and manifest contain the same enforcement values for every principle
- **AND** the principle-application schema publishes the same canonical vocabulary
- **AND** a graph-ordering principle names `applies_to` stages that match explicit `pstack-build` `needs`
- **AND** an evidence principle names its required output artifact or proof record

#### Scenario: Structural coverage is declared, not over-claimed

- **GIVEN** a principle whose rule is represented by a graph edge, expansion, deterministic check, required artifact, or review gate
- **WHEN** the pack metadata and evidence contract are inspected
- **THEN** the corresponding declaration and graph/check/artifact metadata are inspectable
- **AND** the declaration does not claim that an unimplemented formula compiler selected the strongest structural enforcement
- **AND** prose remains methodology guidance for the declared review path

### Requirement: Bug-fix and migration flows preserve pstack ordering

Bug-fix formulas MUST order `reproduce` before problem characterization,
`root-cause` before plan/implementation, and same-surface verification before
completion. Migration formulas MUST declare sequential `callers`, `lever`,
`migrate`, `delete`, and `verify` steps. Refactor formulas MUST declare
`callers` and `verify`. Those steps MAY be ungated. The pack MUST NOT require a
`remaining_callers == 0` field or an absence-check producer that does not exist.

#### Scenario: Bug fix proves the mechanism

- **GIVEN** a reported defect
- **WHEN** `pstack-bug-fix` executes
- **THEN** it records `pstack.reproduction.v1`
- **AND** it records `pstack.root-cause.v1` after hypothesis elimination
- **AND** implementation follows the root-cause artifact
- **AND** verification exercises the same user-visible surface that reproduced the defect

#### Scenario: Legacy API is removed after migration

- **GIVEN** a migration where external compatibility is not required
- **WHEN** `pstack-migration` is inspected as a Gas City formula
- **THEN** it has sequential `callers`, `lever`, `migrate`, `delete`, and `verify` steps
- **AND** `callers` and `delete` may have no producer gate
- **AND** the formula does not declare a `remaining_callers` field or an absence-check producer
