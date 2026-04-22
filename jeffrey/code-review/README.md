# Jeffrey Code Review Pack

Four-pass code review as a Claude skill.

## What It Provides

- Skill overlay at `overlay/.claude/skills/code-review/SKILL.md`
- Invocable as `/code-review` in Claude

The skill runs four sequential passes over a diff, file, or recent changes:

1. **Correctness** — logic, error handling, races, edge cases
2. **Security** — OWASP Top 10 patterns at system boundaries
3. **Performance** — complexity, N+1, unbounded growth, blocking I/O
4. **Maintainability** — naming, abstractions, dead code, coverage gaps

Findings carry a severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `NIT`), a
location, and a suggested fix. The skill closes with a verdict: `APPROVE`,
`REQUEST CHANGES`, or `COMMENT`.

## Import It

```toml
[imports.code-review]
source = "../packs/jeffrey/code-review"
```

## Attribution

Adapted from [Jeffrey Emanuel](https://github.com/Dicklesworthstone)
(@doodlestein)'s Peer Code Reviewer.
