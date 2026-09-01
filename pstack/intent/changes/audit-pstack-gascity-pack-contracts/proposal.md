## Why

The PStack Gas City pack already matches the implemented refresh contract
(compiler requirement, empty doctor delta, `no_removal_opportunity`, vendor pin
`49d6ae8`, host-boundary playbooks). A 2026-08-31 audit found the live OpenSpec
still claims behavior the pack does not execute, while two refresh scenarios
never landed in durable specs. Naive archive of
`refresh-pstack-pack-source-and-formula-requirements` would collide with
hand-synced live files and drop the 14-schema list.

## What Changes

- Record that `pstack-swarm`, `pstack-arena`, and `pstack-interrogate` are
  sequential Gas City formulas with unconsumed `graph_operator` metadata, not
  executed child-graph fanout.
- Record post-pin maintained-source drift as reviewed-but-not-vendored.
- Require the focused pack suite to fail when a formula omits
  `formula_compiler >= 2.0.0`.
- Name the optional methodology catalog that actually exists
  (`compound-engineering`, `superpowers`, `bmad`, `gstack`) and keep action
  integrations outside the pack.
- Treat inspectable formula metadata and disposable live-city listing as the
  metadata evidence class, not an unimplemented cook script.
- Record vendor parity as SHA pin plus runtime-vs-vendor skills digest, not a
  `git archive` of the maintained checkout.
- Record the 21-principle catalog as skill plus manifest, not one committed
  source-binding row per ID.
- Record graph-ordering as `applies_to` stages plus `pstack-build` `needs`.
- Record migration as sequential ungated steps, not `remaining_callers == 0`.
- Drop durable continuation/restart from the focused-test MUST list.
- Adopt sibling selector overrides: pack-local planning assets and
  `lever-decision` on decomposition. Do not copy `contract = "graph.v2"`.
- Pin `vendor/pstack/upstream.toml` to `https://github.com/cursor/plugins`
  path `pstack` commit `6fecddba`. Do not pin `tommy-ca/pstack`.
- Keep host-boundary on pack-owned formulas, assets, and agents. Vendored
  Cursor playbooks may name `watch-pr` and `orch.ts` as upstream text.
- Vendor skills, Cursor plugin agents, README, and LICENSE from that
  Cursor subtree. Keep pack-owned `pstack/agents/` as Gas City role wrappers.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pstack-gascity-pack`: Honest method, catalog, vendor-parity, migration, and test contracts.
- `pstack-pack-fidelity`: Post-pin drift and focused-test MUST list.
- `pstack-delivery-evidence`: Formula compiler metadata is checked in delivery.

## Impact

Affected surfaces are `dev-env/openspec/specs/pstack-*`,
`gascity-packs/pstack/TRACEABILITY.md`, `gascity-packs/pstack/DESIGN.md`, and
focused pack tests. No scheduler, graph-operator interpreter, vendor refresh,
registry entry, or archive of the earlier refresh change is included.
