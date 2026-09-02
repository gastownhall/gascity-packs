## Context

HEAD is `bb6a8c8`. Remaining-gates already locks host sling of
`pstack-poteto-mode` then `pstack-build` as the next operator unit, and it
forbids a registry restamp without those receipts. Disposable live-city
import already has Gherkin under `PStack is exercised through a disposable
live city`. Pack tests still accept the Sources paragraph
`Live city sling remains unproven.` That sentence names neither
`GC_TEST_BIN` nor the two formulas. A live pytest with `GC_TEST_BIN` set
imported pstack into a scratch city (4 passed, 1 skipped because pstack
ships no commands). That run is not a formula sling.

This repository has no `adr/` tree. No in-force ADR constrains the split.

## Goals / Non-Goals

**Goals:**

- TRACEABILITY states import and sling as two sentences.
- Pack tests fail closed if either sentence drops or the old sentence
  returns.
- Live Gherkin records that split as one added scenario on the existing
  TRACEABILITY requirement.

**Non-Goals:**

- No host sling in this change.
- No registry restamp.
- No `gc.provider_panel` stamp.
- No new cook scenarios on `gascity-provider-panel`.
- No rewrite of remaining-gates.
- No land or merge of PR 385.
- No edit of `pstack/REQUIREMENTS.md` in this change.

## Decisions

- Smallest honesty edit. Replace the one conflated Sources sentence.
  Keep the delivery-boundary line that already says live city import and
  formula sling are independent host operations.
- MODIFIED `PStack traceability references durable truth`. Copy the full
  live requirement. Add one scenario. Do not add a second TRACEABILITY
  requirement. Do not restamp remaining-gates.
- Lock the exact sentences in `test_delivery_checks_cover_pstack`. The
  current `assert "unproven" in traceability` stays green on the old
  sentence. Replace that weak check with the two sentences and a ban on
  `Live city sling remains unproven`.
- Keep each locked sentence on its own line in TRACEABILITY so the test
  can match the full string.

## Risks / Trade-offs

- [Risk] `pstack/REQUIREMENTS.md` still says `Live city sling remains unproven.`
  -> Mitigation. Pack tests lock TRACEABILITY, not REQUIREMENTS. Call that
  leftover out in apply notes. Do not grow this change into a docs sweep.
- [Risk] A reader treats the `GC_TEST_BIN` sentence as proof of sling.
  -> Mitigation. The second sentence names both formulas and says unproven.
  Remaining-gates already blocks restamp without those receipts.

## Migration Plan

1. Author this change under `openspec/changes/pstack-live-vs-sling/`.
2. Split the TRACEABILITY sentences. Add the failing test asserts.
3. Validate-only, then archive into this repository `openspec/`.
4. Run `pstack/tests/test_pstack_pack.py`.

## Open Questions

- None.
