## Context

Isolation moved Gherkin into this repository. Archive created
`gascity-provider-panel` with a TBD Purpose. The imported vendor requirement
still said dest-env owns durable Gherkin.

## Goals / Non-Goals

**Goals:**

- Live specs match isolation.
- Tests lock spec files and dest-env absence in pack docs.

**Non-Goals:**

- No formula stamps.
- No dest-env checkout.
- No deletion of `docs/openspec-changes/` in this change.

## Decisions

- Honesty pass is the base. `openspec/specs/` is durable truth.
- Keep `docs/openspec-changes/` as an authoring copy.
- Purpose is prose on the live spec. The vendor sentence is a MODIFIED
  requirement.

## Risks / Trade-offs

- Authoring copy can drift from live specs. Tests lock live files.

## Migration Plan

1. Edit Purpose and vendor requirement.
2. Validate and archive this change.
3. Run pack tests.

## Open Questions

- None.
