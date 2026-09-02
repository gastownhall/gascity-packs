## Why

The live program's Arm boxes ran `git show origin/main:skills/poteto-mode/...`.
Those paths are not in this repository's origin/main. A re-runnable arm list
must name files that exist on trunk.

## What Changes

- Require the live program's `git show origin/main:` list to name files in
  this repository's origin/main.
- Keep the check-plan `origin/main:` substring.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pstack-delivery-evidence`: Live program arm list is re-runnable on trunk.

## Impact

`docs/pstack-program-plan.md` and TRACEABILITY delivery evidence. Formulas
stay unstamped.
