## MODIFIED Requirements

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
