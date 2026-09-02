## ADDED Requirements

### Requirement: City provider panels bind N harnesses without pack provider strings

Feature: gascity-provider-panel

Rule: N-model membership lives in the city. Packs stamp a panel id only.

Gas City MUST accept a city table `[[provider_panels]]` whose `id` is a
stable name and whose `members` are ids already declared under
`[providers.<id>]`. Members MUST be agent harness catalog ids. Members
MUST NOT be `[session].provider` values. Members MUST NOT be model slugs.
Each catalog id carries one frozen model via provider `args`. Formula-managed
daemon work MUST NOT pass `--model` per child. A second model MUST use a
second catalog id. Duplicate `[[rigs.patches]]` rows for one agent MUST
remain a defect. A panel MAY list many members for one role. Missing panel
or a single member MUST lower to sequential fallback on the same formula
name. Cook MUST freeze the member list. Later `city.toml` edits MUST NOT
resize in-flight children.

#### Scenario: Panel members are agent harness ids

- **GIVEN** a city with `[providers.cursor-grok]`, `[providers.antigravity]`, and `[session].provider = "herdr"`
- **WHEN** `[[provider_panels]]` `id = "pstack-arena"` lists `members = ["cursor-grok", "antigravity"]`
- **THEN** cook creates two child beads for a step that stamps `gc.provider_panel = "pstack-arena"`
- **AND** each child carries one provider binding from that frozen list
- **AND** `herdr` is rejected if listed in `members`

#### Scenario: Missing panel is sequential fallback

- **GIVEN** a formula step stamps `gc.provider_panel = "pstack-arena"`
- **AND** the city has no panel with that id
- **WHEN** Gas City cooks the graph
- **THEN** the step remains one bead on `gc.run_target`
- **AND** the formula name does not change

#### Scenario: Panel binding overrides the role patch for child beads

- **GIVEN** `pstack.reviewer` is patched to `codex`
- **AND** a panel lists `cursor-grok` and `antigravity`
- **WHEN** cook expands a review step with that panel id
- **THEN** child beads keep `gc.run_target = "pstack.reviewer"`
- **AND** one child binds `cursor-grok` and the other binds `antigravity`
- **AND** those bindings override the `codex` patch for those beads only
- **AND** sequential steps on `pstack.reviewer` without a panel still use `codex`

#### Scenario: Child id is an opaque slot

- **GIVEN** a panel step stamps `gc.child_artifact_path_template` containing `{child_id}`
- **WHEN** cook assigns child identities
- **THEN** `{child_id}` is a cook-assigned slot
- **AND** the resolved path MUST NOT contain a `[providers.<id>]` name or a model slug

#### Scenario: Child paths and workspaces stay isolated

- **GIVEN** a panel step stamps `gc.child_artifact_path_template` containing `{child_id}`
- **AND** the city panel has two members
- **WHEN** Gas City cooks the graph
- **THEN** each child bead has a distinct resolved artifact path
- **AND** two children MUST NOT share `.gc/pstack/arena-candidate.md`
- **AND** each child has an isolated workspace
- **AND** the synthesizer fan-in list contains those paths and MUST NOT contain provider ids

#### Scenario: One-member panel is sequential fallback

- **GIVEN** `[[provider_panels]]` `id = "pstack-arena"` has exactly one member
- **WHEN** Gas City cooks a step that stamps that panel id
- **THEN** the step remains one bead on `gc.run_target`

#### Scenario: Unknown member is a config error

- **GIVEN** a panel lists a member that is not a `[providers.<id>]` harness
- **WHEN** Gas City loads the city
- **THEN** configuration fails closed
- **AND** cook does not start

#### Scenario: In-flight snapshot ignores later city edits

- **GIVEN** cook froze a three-member panel onto child beads
- **WHEN** `city.toml` later removes a member
- **THEN** in-flight children keep the frozen three-member snapshot

#### Scenario: Unknown panel key is a load error

- **GIVEN** a formula stamps `gc.provider_panel`
- **AND** the formula compiler does not implement provider panels
- **WHEN** Gas City loads the formula
- **THEN** load fails
- **AND** the key is not ignored as inert metadata

#### Scenario: Members are catalog ids not model slugs

- **GIVEN** a city with `[providers.cursor-grok]` whose `args` include `--model cursor-grok-4.5-high`
- **WHEN** a panel lists `members = ["cursor-grok-4.5-high"]`
- **THEN** configuration fails closed
- **AND** cook does not start

#### Scenario: One catalog id cannot multiplex models

- **GIVEN** `[providers.cursor-grok]` with frozen `args` `--model cursor-grok-4.5-high`
- **WHEN** a Formula-managed daemon child binds `cursor-grok`
- **THEN** that child uses `cursor-grok-4.5-high`
- **AND** the city cannot override `--model` on that child without a second catalog id

#### Scenario: Two members with the same frozen model are not diversity

- **GIVEN** two catalog ids whose `args` pin the same `--model`
- **AND** a panel lists both ids
- **WHEN** cook creates two child beads
- **THEN** both beads inherit that same frozen model
- **AND** the pack MUST NOT treat that as N-model diversity

#### Scenario: Pack formulas never name providers

- **GIVEN** a methodology pack formula that uses a provider panel
- **WHEN** pack-owned TOML, assets, and agents are inspected
- **THEN** they contain no provider id strings from `[providers.*]`
- **AND** they contain no Cursor `Task` field names
- **AND** they contain no `spawn_subagent`
