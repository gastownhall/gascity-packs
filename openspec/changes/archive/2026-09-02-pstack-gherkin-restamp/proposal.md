## Why

Archive froze two Gherkin ANDs that live specs later replaced. The vendor
scenario in the archive named dest-env as the Gherkin owner. Live text
forbids naming another project. The arm-list scenario in the archive banned
`pstack/` on origin/main. Live text only forbids plugin `skills/`. If you
restore the `pstack/` ban, PR 385 cannot land isolation.
`apply_intent_change.py` used to default `--change` to
`pstack-delegate-provider-panel`. Omit `--change` and apply copied a payload
into that stale folder, including into `audit-pstack-gascity-pack-contracts`.

## What Changes

- Restamp the vendor Durable Gherkin AND to "another project".
- Restamp the arm-list AND so trunk boxes do not require plugin `skills/`.
- Delete `DEFAULT_CHANGE`. Derive the change name from `--source`.
- Strip a leading `YYYY-MM-DD-` prefix when `--change` is omitted.
- Keep an explicit `--change` as an override.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pstack-gascity-pack`: Durable Gherkin owner is this repository. Apply
  derives the OpenSpec change name from `--source`.
- `pstack-delivery-evidence`: Arm list is re-runnable on trunk without
  plugin `skills/` paths.

## Impact

`openspec/specs/`, `pstack/scripts/apply_intent_change.py`,
`pstack/tests/test_pstack_pack.py`, and the 1.1 boot recipe in
`docs/pstack-program-plan.md`. Formulas stay unstamped. `registry.toml` is
not restamped. `docs/openspec-changes/` stays gone.
