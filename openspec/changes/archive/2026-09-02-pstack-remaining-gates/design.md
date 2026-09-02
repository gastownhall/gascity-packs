## Context

Isolation is on PR 385. Formulas omit `gc.provider_panel`. Host sling is
unproven. The Gas City methodology pack in this repo is not a compiler.
Target cook Gherkin already describes a future stamp. Tests do not lock the
operator sequence.

## Goals / Non-Goals

**Goals:**

- Fail closed if the program drops host sling.
- Fail closed if formulas stamp panel keys.
- Fail closed if `gascity/` grows `provider_panel` in this tree.

**Non-Goals:**

- No host sling in this change.
- No registry restamp.
- No formula stamp.
- No cook implementation of `gascity-provider-panel`.

## Decisions

- ADDED requirement on `pstack-delivery-evidence`. Do not grow cook
  scenarios on `gascity-provider-panel`.
- Dedicated tests, not only the graph_operator freeze. The stamp PR is
  allowed to replace that freeze. A separate omit-stamp test stays until
  an out-of-tree consumer exists.
- The `gascity/` grep is a freeze of this packs tree. It will not flip
  true when the product compiler ships elsewhere. Stamp remains a later
  human-gated PR.

## Risks / Trade-offs

- An empty `gascity/` grep can be misread as “never stamp.” Docs already
  say the compiler is outside this tree.

## Migration Plan

1. Author this change.
2. Add failing tests.
3. Validate and archive.
4. Run pack tests.

## Open Questions

- None.
