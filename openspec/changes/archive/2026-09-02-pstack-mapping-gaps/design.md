## Context

Sibling packs map foreign methodologies onto `build-base`, persona expansion,
and `do-work` drains. pstack already does that for 20 playbook stems and six
method formulas. Audit found three pack-owned holes. Compiler-owned N-model
stays sequential.

## Goals / Non-Goals

**Goals:**

- Name corpus-only skills the way unsupported playbooks are named.
- Make interrogate judgment a checked producer.
- Inherit `do-work` worktree assets on `pstack-work`.

**Non-Goals:**

- No `gc.provider_panel` stamp.
- No `pstack-figure-it-out` formula.
- No persona-split of arena.
- No swarm-as-drain rewrite.

## Decisions

- Put corpus skills in `[corpus].skills` on the existing playbook map file.
  One catalog file. Tests classify every vendor skill directory.
- Gate judgment like arena judge. Schema `gc.build.review.v1`. Path
  `.gc/pstack/interrogate-judgment.md`. Shared `build-artifact-valid.sh`.
- Delete `pstack-work` step overrides for prepare-worktree, implement, and
  close-source-anchor. Keep `extends = ["do-work"]` and
  `implementation_target` default `pstack.implementation-worker`. Compound
  only overrides implement. pstack stubs were worse than no override.
- ARCHITECTURE names `do-work` as the concrete parent of `pstack-work`.

## Risks / Trade-offs

- Inheriting `do-work` implement.md drops the one-line pstack stub. The
  inherited prompt is the worktree contract. Pack policy stays on the
  implementation-worker agent prompt.
- A later `pstack-figure-it-out` formula would need a new change.

## Migration Plan

1. Author this change.
2. Add the failing pack tests.
3. Edit map, interrogate formula, pstack-work, ARCHITECTURE.
4. Validate and archive.
5. Run pack tests.

## Open Questions

- None.
