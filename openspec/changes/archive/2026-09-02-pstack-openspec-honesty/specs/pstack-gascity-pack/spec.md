## MODIFIED Requirements

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
- **AND** it does not name dest-env as the Gherkin owner
