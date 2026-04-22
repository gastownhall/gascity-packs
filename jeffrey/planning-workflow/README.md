# Jeffrey Planning Workflow Pack

Multi-phase plan-before-code workflow as a Claude skill.

## What It Provides

- Skill overlay at `overlay/.claude/skills/planning-workflow/SKILL.md`
- Invocable as `/planning-workflow` in Claude

The skill drives five phases in order — understand, decompose, design,
validate, implement — with the rule that no code is written before validation
is complete.

## Import It

```toml
[imports.planning-workflow]
source = "../packs/jeffrey/planning-workflow"
```

## Attribution

Adapted from [Jeffrey Emanuel](https://github.com/Dicklesworthstone)
(@doodlestein)'s planning workflow.
