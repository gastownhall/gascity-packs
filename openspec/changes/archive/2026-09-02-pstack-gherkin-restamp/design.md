## Context

Live specs drifted after archive. The vendor AND now says "another project".
The arm-list AND now forbids plugin `skills/` only. Apply used to default
`--change` to `pstack-delegate-provider-panel`. `--source` is already
required. The source directory already names the payload.

## Goals / Non-Goals

**Goals:**

- Archive records the live ANDs.
- Omitting `--change` cannot copy into `pstack-delegate-provider-panel`.
- Dated archive folders map to undated OpenSpec change names.

**Non-Goals:**

- No formula stamps.
- No `registry.toml` restamp.
- No `docs/openspec-changes/` restore.
- No `pstack/` ban on origin/main.
- No extra apply framework.
- No fifth isolation-ownership capability.

## Decisions

- Copy each live requirement in full. Edit only the drifted AND. Do not
  rewrite vendor or TRACEABILITY prose.
- Put the new CLI rule in ADDED. Do not mix it into the vendor corpus
  requirement.
- Delete `DEFAULT_CHANGE` first. Then derive the name from `--source`.
- The change name is a function of the source directory name and an
  optional `--change`. Do not keep a module-level default name.
- Strip one leading `YYYY-MM-DD-` prefix when `--change` is omitted.
  `2026-09-02-pstack-program-arm-list` becomes `pstack-program-arm-list`.
- An explicit `--change` wins, dated or not.
- One helper and one regex in `apply_intent_change.py`. No name registry.
- Archive from a `--source` outside `pstack/` and outside the dest path
  `openspec/changes/pstack-gherkin-restamp`. `copy_change` deletes dest
  before copy.

## Risks / Trade-offs

- A source directory with no date prefix and a wrong basename needs
  `--change`. The helper does not guess.
- Pytest count in 1.1 moves from 44 passed to 45 passed.

## Migration Plan

1. Keep the payload ANDs as live text.
2. Add the failing pack test for the arm-list archive without `--change`.
3. Delete `DEFAULT_CHANGE` and derive the name.
4. Drop `--change` from the 1.1 boot recipe. Update 44 passed to 45.
5. Validate this payload from a source path that is not the dest copy.
6. Archive into this repository `openspec/`.
7. Run pack tests.

## Open Questions

- None.
