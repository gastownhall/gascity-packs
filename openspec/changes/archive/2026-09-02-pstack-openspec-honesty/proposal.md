## Why

Archive left a TBD Purpose on `gascity-provider-panel` and a dest-env ownership
sentence in the vendor requirement. This repository owns Gherkin. Those lines
are false.

## What Changes

- Fill the panel spec Purpose.
- Record that durable Gherkin lives at repository `openspec/specs/`.
- Require apply to refuse `pstack/` sources. Do not name dest-env as owner.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pstack-gascity-pack`: Vendor rule owns Gherkin in this repository.

## Impact

Pack docs, tests, and `openspec/specs/`. Formulas stay unstamped.
