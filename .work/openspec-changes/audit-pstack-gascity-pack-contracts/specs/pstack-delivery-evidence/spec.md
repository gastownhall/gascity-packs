## ADDED Requirements

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
catalog strings MUST NOT claim Gas City expands `gc.graph_operator`.

#### Scenario: Catalog strings do not claim executed fanout

- **GIVEN** `pstack-swarm`, `pstack-arena`, and `pstack-interrogate` catalog descriptions
- **WHEN** an operator lists formulas
- **THEN** the text says sequential frames
- **AND** the text does not claim Gas City expands `gc.graph_operator`

### Requirement: Operator docs do not advertise a slung main import

Feature: pstack-delivery-evidence

Rule: README and TRACEABILITY match the unslung catalog pin

`pstack/README.md` MUST document a local clone import as the working command.
The GitHub `gc import add` URL MAY remain as the intended form. It MUST say
that URL works only when the imported git ref contains `pstack/`. It MUST say
registry `0.1.0` is a catalog pin, not a slung production release. It MUST say
method formulas are sequential annotated steps and MUST NOT claim
multi-provider fanout. Root `README.md` MUST say pstack is not a slung
production import. `pstack/TRACEABILITY.md` MUST forbid restamping `commit` or
`hash` without a host sling of `pstack-poteto-mode` and `pstack-build`.

#### Scenario: Pack README leads with a local clone

- **GIVEN** `pstack/README.md`
- **WHEN** an operator follows Quick start step 1
- **THEN** the working import is `[imports.pstack] source = "../gascity-packs/pstack"`
- **AND** the GitHub `gc import add` URL is present
- **AND** the text says the URL works only when the imported git ref contains `pstack/`
- **AND** the text says registry `0.1.0` is not a slung production release
- **AND** the text says method formulas are not multi-provider fanout

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

#### Scenario: Method skills stay off the playbook map

- **GIVEN** `pstack/mappings/playbooks.toml`
- **WHEN** the focused pack tests run
- **THEN** `how`, `why`, `swarm`, `arena`, and `interrogate` are absent from `[playbooks]`
- **AND** those stems are absent from `[unsupported].stems`
- **AND** the file has no `[methods]` table
