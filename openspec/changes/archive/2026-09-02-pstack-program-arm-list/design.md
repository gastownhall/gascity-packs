## Context

check-plan.mjs requires `git show origin/main:` in Arm the program. The
copied pstack plugin skill paths do not exist on gascity-packs origin/main.

## Goals / Non-Goals

**Goals:**

- Arm list re-runs on trunk.
- Live program still passes check-plan.mjs.

**Non-Goals:**

- No formula stamps.
- No pstack files required on origin/main before PR 385 lands.

## Decisions

- Name ci.yml, registry.toml, README.md, gascity/pack.toml, bmad/pack.toml,
  superpowers/pack.toml, and validate_registry.py.
- Execution playbook stays named in How to read this.

## Risks / Trade-offs

- Plugin playbooks are not re-read from this repo's trunk. They live in the
  host plugin.

## Migration Plan

1. Edit the arm list.
2. Archive this change.
3. Run pack tests and check-plan.mjs.

## Open Questions

- None.
