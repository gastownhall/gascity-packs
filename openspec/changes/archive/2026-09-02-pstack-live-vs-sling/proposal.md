## Why

`pstack/TRACEABILITY.md` folds disposable live-city import into one sentence,
`Live city sling remains unproven.` Disposable import already ran at HEAD
`bb6a8c8` when `GC_TEST_BIN` was set. Formula sling of `pstack-poteto-mode`
and `pstack-build` did not.

## What Changes

- Split that TRACEABILITY note into two sentences. Disposable live-city
  import is exercised when `GC_TEST_BIN` is set. Formula sling of
  `pstack-poteto-mode` and `pstack-build` remains unproven.
- Pack tests lock both sentences and reject the old one.
- Add one scenario on the delivery-evidence TRACEABILITY requirement.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pstack-delivery-evidence`: TRACEABILITY must split disposable live-city
  import from formula sling.

## Impact

`pstack/TRACEABILITY.md`, `pstack/tests/test_pstack_pack.py`, and
`openspec/specs/pstack-delivery-evidence/spec.md`. Formulas stay unstamped.
`registry.toml` is not restamped. Cook Gherkin on `gascity-provider-panel`
does not grow. This change does not land PR 385.
