## Context

Prior audit on `feat/pstack-pack-honesty` showed `pstack-arena` and
`pstack-interrogate` as sequential graphs. `gc.graph_operator` is inert.
`pstack-build-review` is the only live expansion. Its children share
`pstack.reviewer`, so they share one city provider. Duplicate
`[[rigs.patches]]` rows for one agent are a city defect.

Two architect sketches ran. Named-slot expansion (four pack agent names)
works on `formula_compiler >= 2.0.0`. A city provider panel needs a Gas
City cook change and keeps one role name.

## Goals / Non-Goals

**Goals:**

- Document how a city binds N models without pack Task spawn.
- Record the panel as the N-model primitive in this repository OpenSpec.
- Keep this checkout's formulas sequential until the consumer exists.

**Non-Goals:**

- No `graph_operator` interpreter in the pack or in `gascity/` this change.
- No eight named runner agents in this checkout.
- No restamp of registry `0.1.0`.

## Decisions

- Base sketch is the city provider panel. N lives in `city.toml`.
- Reject named-slot expansion as the durable pack shape. It freezes N in
  pack TOML and multiplies `gc-role-worker` wrappers.
- Keep named-slot expansion as a city overlay recipe only.
- Subtract Beads-child instructions from `fanout.md`. Workers must not
  invent children.
- Stamp `gc.provider_panel` only after Gas City records a consumer and a
  compiler floor above `2.0.0`.
- `[session].provider` stays Herdr. Panel members are `[providers.*]` catalog ids.
- Model selection is `args` on that catalog id. Formula daemon work cannot pass `--model` per child.
- Sibling pack expansions stay persona lanes. They are not the N-model primitive.

## Risks / Trade-offs

- Docs describe a target the current formulas do not execute. README
  still says sequential graphs and `does not expand gc.graph_operator`.
- Gas City cook is runtime work. This repository owns Gherkin only.
- Isolated paths in a shared worktree still allow repo-edit collisions
  until Gas City assigns per-child workspaces.

## Migration Plan

1. Land pack docs and this OpenSpec change payload outside `pstack/`.
2. Validate with `pstack/scripts/apply_intent_change.py --validate-only`.
3. Archive into this repository `openspec/specs/`.
4. Implement panel cook in Gas City.
5. Stamp pack formulas in a later PR.

## Open Questions

- What compiler version string Gas City will assign when panel cook ships.
- Whether interrogate judgment uses `pstack.interrogate-judgment.v1` or
  gated `gc.build.review.v1` in the formula PR.
