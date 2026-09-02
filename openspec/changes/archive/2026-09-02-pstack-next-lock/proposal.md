## Why

Live Gherkin already says TRACEABILITY does not name another project as the
Gherkin owner. Pack tests only grep a dest-env token. A foreign owner under
other wording stays green. Arena judge is a gated producer with a one-line
asset, unlike interrogate judgment.

## What Changes

- Pack tests fail closed on the restamped Gherkin AND, not only dest-env.
- Arena judge names the `pstack.arena-synthesis.v1` producer contract.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pstack-delivery-evidence`: Tests lock the restamped Gherkin owner AND.

## Impact

`pstack/tests/test_pstack_pack.py`, `pstack/assets/workflows/pstack-methods/arena-judge.md`.
Formulas stay unstamped. Host sling and panel stamp stay out of this change.
