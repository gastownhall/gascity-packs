## Context

Arena picked one master plan over three stacked files plus an index.

## Goals / Non-Goals

**Goals:**

- One live program file.
- TRACEABILITY points at it.

**Non-Goals:**

- No formula stamps.
- No dest-env node.

## Decisions

- `pr-pstack-land-honesty` is PR 385.
- `pr-pstack-panel-stamp` waits on a Gas City compiler consumer.
- Old plan files are one-line pointers.

## Risks / Trade-offs

- Pointer files drop historical checklists. The program plan holds the graph.

## Migration Plan

1. Land `docs/pstack-program-plan.md`.
2. Archive this change.
3. Run pack tests.

## Open Questions

- None.
