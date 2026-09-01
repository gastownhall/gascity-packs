## Why

Live dest-env Gherkin still describes a complete Cursor documentation and
automation corpus, `git archive` byte parity, and vendored playbooks that must
not name `watch-pr`. The live pack vendors a listed Cursor subset, greps
host-boundary strings on pack-owned files, and keeps OpenSpec payloads out of
`pstack/`. Naive archive of
`refresh-pstack-pack-source-and-formula-requirements` would collide with
hand-synced live files.

## What Changes

- Restate vendor parity as Cursor `plugins` path `pstack` commit `6fecddba`,
  listed paths `skills`, `agents`, `README`, and `LICENSE`, plus runtime-vs-vendor
  skills digest. Do not require a `git archive` of Cursor `main`.
- Keep host-boundary on pack-owned formulas, assets, and agents. Vendored
  Cursor playbooks may name `watch-pr` and `orch.ts` as upstream text.
- Record that the pack does not ship `pstack/intent/`. Dest-env owns durable
  Gherkin. `apply_intent_change.py` requires `--source` outside the pack.
- Record that `pstack-swarm`, `pstack-arena`, and `pstack-interrogate` are
  sequential Gas City formulas with unconsumed `graph_operator` metadata, not
  executed child-graph fanout.
- Record that operator README documents a local clone import. Registry `0.1.0`
  is a catalog pin, not a slung production release. Method skill stems stay off
  `playbooks.toml`.
- Record post-pin Cursor `main` differences as reviewed-but-not-vendored drift.
  Do not name a moving maintained SHA as the durable pin. Do not pin
  `tommy-ca/pstack`.
- Require the focused pack suite to fail when a formula omits
  `formula_compiler >= 2.0.0` or retains `contract = "graph.v2"`.
- Name the five derived methodology packs already in dest-env's derived-pack
  compatibility suite: `compound-engineering`, `superpowers`, `bmad`,
  `gstack`, and `pstack`.
- Name the optional methodology catalog that exists
  (`compound-engineering`, `superpowers`, `bmad`, `gstack`) and keep action
  integrations outside the pack.
- Drop durable continuation/restart from the focused-test MUST list.
- Record migration as sequential ungated steps, not `remaining_callers == 0`.
- Adopt sibling selector overrides. Do not copy `contract = "graph.v2"`.
- Do not add dest-env pack-catalog Gherkin for registry `0.1.0`. That catalog
  already exists in gascity-packs installer, CI, supported-pack nightly, and
  inference. Dest-env has no pack-catalog requirement.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pstack-gascity-pack`: Honest vendor, host-boundary, method, catalog, migration, and test contracts.
- `pstack-pack-fidelity`: Cursor pin, pack-owned host-boundary, and focused-test MUST list.
- `pstack-delivery-evidence`: Formula compiler metadata is checked in delivery.

## Impact

Affected surfaces are `dev-env/openspec/specs/pstack-*`. Pack TRACEABILITY,
ARCHITECTURE, formulas, and focused tests match sequential method honesty.
Catalog README honesty is in the working tree until committed on PR 385. No
scheduler, graph-operator interpreter, moving Cursor `main` pin, dest-env
pack-catalog requirement, or archive of the earlier refresh change is
included. Cursor product guide docs are not vendored.
