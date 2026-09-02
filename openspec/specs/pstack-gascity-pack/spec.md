# pstack-gascity-pack Specification

## Purpose

Define the pstack Gas City methodology pack, its derived build contract, evidence boundaries, and providerless composition rules.

## Requirements

### Requirement: Pack-local schemas resolve through producer context

The shared build-artifact producer gate MUST derive pack-specific schema lookup from the resolved `GC_PACK_DIR` when that pack contains a `schemas/` directory. It MUST prepend that directory to `GC_BUILD_SCHEMA_ROOTS` after the shared Gas City schema root, and producers MUST NOT need to set `GC_BUILD_SCHEMA_ROOTS` themselves to validate a PStack-specific artifact.

#### Scenario: PStack producer validates a pack-local artifact

- **GIVEN** a PStack producer runs the shared artifact gate with `GC_PACK_DIR` set to the resolved PStack pack root
- **AND** the producer records `pstack.program-status.v1` and a relative artifact path in its step metadata
- **WHEN** the gate validates the produced artifact
- **THEN** it resolves `pstack.program-status.v1` from the PStack pack's `schemas/` directory
- **AND** it returns success without a caller-supplied `GC_BUILD_SCHEMA_ROOTS`

#### Scenario: Shared schemas retain precedence

- **GIVEN** a pack-local schema root and the shared Gas City schema root are both available
- **WHEN** the producer gate resolves a schema ID published by Gas City
- **THEN** it uses the shared schema definition first
- **AND** the pack-local root can only add new schema IDs, not shadow or relax shared contracts

### Requirement: Pack follows the Gas City derived-methodology contract

The `pstack` directory in `gastownhall/gascity-packs` MUST be a schema-2 pack importing Gas City as `[imports.gc]` and MUST expose `pstack-build` as a derived `build-base` formula. `pstack-build` MUST preserve the base anchor order and use the standard selector interfaces `planning_formula`, `decomposition_formula`, `implementation_formula`, `implementation_item_formula`, `code_review_formula`, and `review_fix_formula`.

#### Scenario: Pack resolves through the base import

- **GIVEN** a Gas City packs checkout containing `pstack/pack.toml`
- **WHEN** the pack metadata is parsed
- **THEN** the pack declares `name = "pstack"` and `schema = 2`
- **AND** `[imports.gc]` points at the sibling `gascity` pack
- **AND** `pstack-build` extends `build-base`

#### Scenario: Build anchors remain ordered

- **GIVEN** the resolved `pstack-build` formula
- **WHEN** its graph is inspected
- **THEN** the base anchors occur in order: `prepare`, `requirements`, `plan`, `plan-review`, `decompose`, `implement`, `implement-same-session`, `summarize-implementation`, `review`, `finalize`, `publish`
- **AND** any PStack-specific steps declare explicit insertion points, outputs, and dependencies

#### Scenario: Standard mode vocabulary is accepted

- **GIVEN** a `pstack-build` invocation
- **WHEN** it receives mode variables
- **THEN** `interaction_mode` accepts only `interactive`, `autonomous`, or `headless`
- **AND** `review_mode` accepts only `report`, `agent`, or `interactive`
- **AND** `drain_policy` accepts only `separate` or `same-session`
- **AND** `implementation_strategy` uses `drain` or `convoy-step`

### Requirement: Upstream pstack corpus is exact and traceable

Feature: pstack-gascity-pack

Rule: Vendor is the reviewed Cursor listed subset, not a complete documentation corpus

The pack MUST vendor official Cursor pstack as the canonical methodology
corpus. `vendor/pstack/upstream.toml` MUST set `source` to
`https://github.com/cursor/plugins`, `path` to `pstack`, and `commit` to
`6fecddba65801f9b9c08b8b328d998ee5b09d290`. The pack MUST NOT pin
`tommy-ca/pstack` or any other host port as upstream. Pack shape follows
gascity-packs methodology packs (`bmad`, `superpowers`, `gstack`,
`compound-engineering`) extending Gas City virtual contracts. The listed
vendor paths MUST be `vendor/pstack/skills`, `vendor/pstack/agents`,
`vendor/pstack/README.md`, and `vendor/pstack/LICENSE`. Guide docs and Benny
automations MUST NOT be vendored. `vendor/pstack/README.md` MUST name the
Gas City listed subset and the GitHub URL of the uncopied Cursor guide.
Cursor plugin agent markdown MUST live under `vendor/pstack/agents/` and MUST
NOT replace pack-owned `pstack/agents/` Gas City role wrappers. Runtime
`skills/` MUST match `vendor/pstack/skills/` byte-for-byte. Formulas MUST NOT
use `SKILL.md` as `description_file`. Gas City mapping MUST live in pack-owned
formulas, assets, and agents. Pack-owned files MUST NOT prescribe
`scripts/watch-pr/watch-pr` or `scripts/orch/orch.ts`. Vendored Cursor
playbooks MAY contain those paths as upstream text. Tests MUST NOT require a
`git archive` of Cursor `main`. Tests MUST NOT require a tommy-ca URL. The
pack MUST NOT ship `pstack/intent/changes/`. Durable Gherkin lives at
repository `openspec/`. `pstack/scripts/apply_intent_change.py` MUST refuse
paths under `pstack/`.

`pstack/ARCHITECTURE.md` MUST record the building-block map from Cursor
playbooks and principles onto Gas City formulas and primitives.

#### Scenario: Vendor parity is checked

- **GIVEN** the recorded pstack upstream revision
- **WHEN** the focused pack tests run
- **THEN** `vendor/pstack/upstream.toml` records source `https://github.com/cursor/plugins`, path `pstack`, and commit `6fecddba65801f9b9c08b8b328d998ee5b09d290`
- **AND** all 21 canonical principle skill directories are present under runtime `skills/`
- **AND** runtime `skills/` matches `vendor/pstack/skills/` byte-for-byte
- **AND** pack-owned formulas, assets, and agents contain no `scripts/watch-pr` or `scripts/orch/orch.ts` live path
- **AND** a vendored Cursor playbook that names those paths does not fail the host-boundary check
- **AND** `vendor/pstack/upstream.toml` `[vendor].paths` lists skills, agents, README, and LICENSE
- **AND** `vendor/pstack/agents/comment-sicko.md` and `vendor/pstack/agents/poteto-agent.md` exist
- **AND** pack-owned `pstack/agents/` still contains Gas City role directories
- **AND** `vendor/pstack/docs` and `vendor/pstack/automations` do not exist
- **AND** `vendor/pstack/README.md` names the Gas City listed subset and the GitHub Cursor guide URL
- **AND** `pstack/intent/` does not exist
- **AND** the suite does not compare the vendor tree to a `git archive` of Cursor `main`

#### Scenario: Runtime prompts do not mutate source material

- **GIVEN** a Gas City formula or role prompt that adapts pstack behavior
- **WHEN** the prompt is resolved
- **THEN** it references vendored methodology or a pack-owned mapping
- **AND** it does not rewrite the vendored file or dispatch through a provider-native durable API

#### Scenario: Discipline source stays Cursor pstack

- **GIVEN** `pstack/TRACEABILITY.md` and `pstack/ARCHITECTURE.md`
- **WHEN** a reader follows the discipline source
- **THEN** TRACEABILITY names `https://github.com/cursor/plugins/tree/main/pstack` and commit `6fecddba65801f9b9c08b8b328d998ee5b09d290`
- **AND** `vendor/pstack/upstream.toml` records that same Cursor plugins commit as the vendor pin
- **AND** ARCHITECTURE names `build-base` and sibling methodology packs as the packing reference
- **AND** neither file pins `tommy-ca/pstack`

#### Scenario: OpenSpec payload stays outside the pack

- **GIVEN** `pstack/scripts/apply_intent_change.py` and the pack tree
- **WHEN** validate-only is invoked with `--source` set to the pack root
- **THEN** the command exits non-zero
- **AND** it reports that OpenSpec payloads do not live inside the pack
- **AND** a later archive uses `--source` outside `pstack/`

#### Scenario: Durable Gherkin lives in this repository

- **GIVEN** `pstack/TRACEABILITY.md` and `openspec/specs/pstack-gascity-pack/spec.md`
- **WHEN** a reader follows the durable specification
- **THEN** TRACEABILITY names `openspec/specs/pstack-gascity-pack/spec.md`
- **AND** it does not name another project as the Gherkin owner

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

### Requirement: Principle-specific artifacts use stable schemas

The pack MUST define namespaced schemas only for genuinely PStack-specific semantic objects and MUST validate them at producer graph nodes.
Required schemas are `pstack.source-binding.v1`, `pstack.principle-application.v1`, `pstack.foundation.v1`, `pstack.lever-decision.v1`, `pstack.reproduction.v1`, `pstack.root-cause.v1`, `pstack.verification.v1`, `pstack.arena-candidate.v1`, `pstack.arena-synthesis.v1`, `pstack.swarm-result.v1`, `pstack.decision.v1`, `pstack.frontier.v1`, `pstack.standing-orders.v1`, and `pstack.program-status.v1`.
Schemas MUST derive shared identifiers and revision fields from existing Gas City/Beads contracts rather than inventing duplicate generic build objects. Every PStack schema MUST declare the shared coverage-status vocabulary and `producer.attempt` so pack-local artifacts remain valid inputs to the shared validator. The `pstack.decision.v1` schema MUST accept `status: no_removal_opportunity` while retaining non-empty `subtraction` and `rationale` requirements.

#### Scenario: Source binding records a translation

- **GIVEN** a vendored skill or playbook mapped to a Gas City formula node
- **WHEN** the mapping is recorded
- **THEN** `pstack.source-binding.v1` contains `id`, source `path`, `section`, immutable `commit`, target formula/node, realization type, status, and rationale
- **AND** the binding distinguishes implemented, delegated, source-only, and unsupported behavior

#### Scenario: Principle application records an actual decision

- **GIVEN** an applicable principle changes a workflow or implementation decision
- **WHEN** the formula completes that decision
- **THEN** `pstack.principle-application.v1` records the principle, trigger, decision, effect, enforcement kind, evidence references, and status
- **AND** a principle is not credited merely because its skill body was loaded

#### Scenario: Verification binds to a revision

- **GIVEN** a commit, PR, runtime, or artifact is reviewed
- **WHEN** PStack verification completes
- **THEN** `pstack.verification.v1` records subject kind/id, revision, checks, evidence references, and a verdict of `verified`, `failed`, `blocked`, or `insufficient`
- **AND** static or metadata evidence cannot claim runtime/provider execution

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
registry alongside `compound-engineering`, `superpowers`, `bmad`, and
`gstack`, and MUST add focused tests for exact 21-principle parity,
manifest/enforcement coverage, source traceability, formula anchor ordering,
selector compatibility, standard schemas, providerless routes, principle
ordering, revision-bound verification, formula compiler requirements, the
explicit no-removal status, pack-owned host-boundary strings, unconsumed
graph-operator metadata, reviewed-but-not-vendored source drift, and the
absence of pack-local OpenSpec payloads. Tests MUST fail closed when these
contracts regress. Metadata evidence MUST be inspectable formula TOML plus
disposable live-city formula and agent listing. Tests MUST NOT require a
separate graph-cook script. A `restart_token` field on
`pstack.program-status.v1` is schema data, not a continuation-semantics suite.

#### Scenario: Derived-pack suite includes PStack

- **GIVEN** the existing `gascity/tests/test_derived_pack_compatibility.py` registry
- **WHEN** the Gas City pack test suite runs
- **THEN** `pstack` is checked alongside `compound-engineering`, `superpowers`, `bmad`, and `gstack`
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

- **GIVEN** a formula retains a deprecated graph contract or omits its compiler requirement, a decision schema rejects the documented no-removal status, or a pack-owned asset restores a forbidden local path
- **WHEN** the focused PStack and shared Gas City tests run
- **THEN** they fail with the violated contract
- **AND** no partial compatibility result is accepted

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
