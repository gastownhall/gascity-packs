# pstack-delivery-evidence Specification

## Purpose

Define CI and disposable live-city coverage for the PStack pack.

## Requirements

### Requirement: PStack delivery checks run in CI

The pack repository CI MUST run the PStack pack test suite and `gc lint pstack` alongside the existing pack checks. These checks MUST inspect the checkout being tested and MUST fail the job when PStack's pack contracts regress.

#### Scenario: PStack pack tests are part of the Python CI command

- **GIVEN** the repository CI workflow runs its Python test step
- **WHEN** the workflow checks out the repository
- **THEN** it invokes `pstack/tests/test_pstack_pack.py` with the shared pytest command
- **AND** a failing PStack test fails the CI job

#### Scenario: PStack is part of the Gas City lint loop

- **GIVEN** the repository CI workflow runs its pack lint step
- **WHEN** the workflow iterates over maintained lint targets
- **THEN** it invokes `gc lint pstack`
- **AND** a PStack lint error fails the CI job

### Requirement: PStack is exercised through a disposable live city

The maintained-pack live test matrix MUST import PStack into a scratch city with the real Gas City CLI. It MUST derive PStack's formulas and agents from its checkout, verify that each resolves through the imported city, and assert the observed doctor delta against an explicit expected set. The live test MUST retain the canary control that proves doctor findings are being surfaced. Every PStack formula MUST declare `formula_compiler >= 2.0.0` and MUST NOT retain deprecated `contract = "graph.v2"`; the expected PStack-specific doctor delta MUST be empty.

#### Scenario: PStack formulas and agents resolve through Gas City

- **GIVEN** a real executable Gas City CLI is provided to the live test fixture
- **WHEN** a scratch city imports only the PStack pack under test
- **THEN** every formula discovered under `pstack/formulas/` is listed by `gc formula list`
- **AND** every agent discovered under `pstack/agents/` is listed by `gc agent list`
- **AND** no provider, publication, or canonical city state is mutated

#### Scenario: PStack doctor delta is explicit

- **GIVEN** the scratch city and equivalent baseline city are inspected by `gc doctor`
- **WHEN** the PStack delta is computed
- **THEN** the expected PStack-specific delta is empty
- **AND** the live suite records no additional PStack-specific finding
- **AND** the canary control continues to observe its intentional `formula-requirements` finding

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

### Requirement: Formula requirement metadata is checked in delivery

Feature: pstack-delivery-evidence

Rule: Compiler requirements fail in the focused suite

The PStack pack test suite MUST check that every discovered PStack formula
contains the supported formula compiler requirement
`formula_compiler >= 2.0.0` and MUST NOT retain deprecated
`contract = "graph.v2"` before the live matrix is used as delivery evidence.

#### Scenario: Missing formula requirement fails the focused check

- **GIVEN** a PStack formula omits `requires.formula_compiler`
- **WHEN** the pack conformance test runs
- **THEN** it fails before accepting the delivery contract

#### Scenario: Deprecated graph contract fails the focused check

- **GIVEN** a PStack formula retains `contract = "graph.v2"`
- **WHEN** the pack conformance test runs
- **THEN** it fails before accepting the delivery contract

### Requirement: First registry publication waits on host dogfood

Feature: pstack-delivery-evidence

Rule: Catalog pin on gastownhall main is not the first live city

The pack MUST NOT treat an unmerged registry `0.1.0` pin as a gastownhall
`main` import. First publication MUST follow a host city that imports the
checkout path and slings `pstack-poteto-mode` plus `pstack-build`. Formula
catalog strings MUST NOT claim Gas City expands `gc.graph_operator`. Catalog
strings MUST describe the current sequential graphs. They MUST NOT claim this
checkout cooks `gc.provider_panel`.

#### Scenario: Catalog strings do not claim executed fanout

- **GIVEN** `pstack-swarm`, `pstack-arena`, and `pstack-interrogate` catalog descriptions
- **WHEN** an operator lists formulas
- **THEN** the text says sequential frames
- **AND** the text does not claim Gas City expands `gc.graph_operator`
- **AND** the text does not claim this checkout expands `gc.provider_panel`

### Requirement: Operator docs do not advertise a slung main import

Feature: pstack-delivery-evidence

Rule: README and TRACEABILITY match the unslung catalog pin

`pstack/README.md` MUST document a local clone import as the working command.
The GitHub `gc import add` URL MAY remain as the intended form. It MUST say
that URL works only when the imported git ref contains `pstack/`. It MUST say
registry `0.1.0` is a catalog pin, not a slung production release. It MUST say
method formulas in this checkout are sequential annotated steps and MUST NOT
claim this checkout executes multi-provider fanout. It MAY describe a
`[[provider_panels]]` cook as a target that is not executed until a compiler
consumes `gc.provider_panel`. Root
`README.md` MUST say pstack is not a slung production import.
`pstack/TRACEABILITY.md` MUST forbid restamping `commit` or `hash` without a
host sling of `pstack-poteto-mode` and `pstack-build`.

#### Scenario: Pack README leads with a local clone

- **GIVEN** `pstack/README.md`
- **WHEN** an operator follows Quick start step 1
- **THEN** the working import is `[imports.pstack] source = "../gascity-packs/pstack"`
- **AND** the GitHub `gc import add` URL is present
- **AND** the text says the URL works only when the imported git ref contains `pstack/`
- **AND** the text says registry `0.1.0` is not a slung production release
- **AND** the text says method formulas are not multi-provider fanout

#### Scenario: README may name the unarchived panel target

- **GIVEN** `pstack/README.md` How N-model fanout will work
- **WHEN** an operator reads the target
- **THEN** the text names `[[provider_panels]]` as city configuration
- **AND** the text says the pack stamps `gc.provider_panel` only after the compiler consumes that key
- **AND** the text still says this checkout runs sequential graphs

#### Scenario: TRACEABILITY forbids restamp without a host sling

- **GIVEN** `pstack/TRACEABILITY.md`
- **WHEN** a reader follows the delivery boundary
- **THEN** it names registry `0.1.0` as the first catalog pin
- **AND** it says that pin is not a slung production release
- **AND** it forbids restamping `commit` or `hash` without a host sling

### Requirement: Playbook map excludes method skill stems

Feature: pstack-delivery-evidence

Rule: how, why, swarm, arena, and interrogate are sling names, not playbook stems

`pstack/mappings/playbooks.toml` MUST map Cursor playbook stems only. It MUST
NOT contain keys `how`, `why`, `swarm`, `arena`, or `interrogate`. It MUST NOT
contain a `[methods]` table until a later packing change adds one on purpose.
It MUST list corpus-only Cursor skills under `[corpus].skills`. Those skills
MUST NOT have sling formulas.

#### Scenario: Method skills stay off the playbook map

- **GIVEN** `pstack/mappings/playbooks.toml`
- **WHEN** the focused pack tests run
- **THEN** `how`, `why`, `swarm`, `arena`, and `interrogate` are absent from `[playbooks]`
- **AND** those stems are absent from `[unsupported].stems`
- **AND** the file has no `[methods]` table

#### Scenario: Corpus-only skills are named

- **GIVEN** `pstack/mappings/playbooks.toml` and `pstack/vendor/pstack/skills/`
- **WHEN** the focused pack tests run
- **THEN** `[corpus].skills` names every vendor skill directory that is not a principle, not `poteto-mode`, and not backed by a `pstack-<name>` formula
- **AND** none of those corpus skills have a sling formula

### Requirement: Remaining program units stay host sling then compiler then panel stamp

Feature: pstack-delivery-evidence

Rule: Isolation on PR 385 does not authorize restamp or panel stamp

The live program MUST name host sling of `pstack-poteto-mode` then
`pstack-build` as the next operator unit after `pr-pstack-land-honesty` is on
PR 385. That unit MUST NOT be a GitHub PR. Restamp of registry `0.1.0` MUST
wait on those sling receipts. `pstack/TRACEABILITY.md` MUST name both formulas
on the restamp gate. The program MUST say `pr-pstack-panel-stamp` must not
start on Gherkin alone. Pack tests MUST fail if any
`pstack/formulas/*.formula.toml` contains `gc.provider_panel` or
`gc.child_artifact_path_template`. Pack tests MUST fail if `gascity/` contains
`provider_panel`. Presence of `openspec/specs/gascity-provider-panel/spec.md`
MUST NOT authorize a formula stamp.

#### Scenario: Host sling is the next operator unit

- **GIVEN** `docs/pstack-program-plan.md`
- **WHEN** an operator follows the spawn graph after isolation is on PR 385
- **THEN** the next unit names host sling of `pstack-poteto-mode` and `pstack-build`
- **AND** that unit is not a GitHub PR
- **AND** restamp of `registry.toml` 0.1.0 waits on sling receipts

#### Scenario: TRACEABILITY names both sling formulas on the restamp gate

- **GIVEN** `pstack/TRACEABILITY.md`
- **WHEN** a reader follows the delivery boundary
- **THEN** it forbids restamping `commit` or `hash` without a host sling
- **AND** that sentence names `pstack-poteto-mode` and `pstack-build`

#### Scenario: Panel stamp does not start on Gherkin alone

- **GIVEN** `docs/pstack-program-plan.md` and `openspec/specs/gascity-provider-panel/spec.md`
- **WHEN** an operator considers `pr-pstack-panel-stamp`
- **THEN** the program says the compiler is outside this packs tree
- **AND** it says `pr-pstack-panel-stamp` must not start on Gherkin alone
- **AND** pack formulas still omit `gc.provider_panel`

#### Scenario: Tests fail closed on a premature panel stamp

- **GIVEN** `pstack/tests/test_pstack_pack.py`
- **WHEN** the focused pack tests run
- **THEN** every `pstack/formulas/*.formula.toml` omits `gc.provider_panel`
- **AND** every such file omits `gc.child_artifact_path_template`
- **AND** `gascity/` has no `provider_panel` hit

## Non-Goals

- Adding PStack to `registry.toml` or publishing a release.
- Claiming provider execution, remote worker execution, or canonical-city mutation from disposable live-city checks.
