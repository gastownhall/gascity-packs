## MODIFIED Requirements

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
