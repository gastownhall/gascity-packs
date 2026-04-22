# Jeffrey README Revise Pack

Evaluate and polish project documentation, via a Claude skill.

## What It Provides

- Skill overlay at `overlay/.claude/skills/readme-revise/SKILL.md`
- Invocable as `/readme-revise` in Claude

The skill walks a checklist (one-sentence purpose, install instructions,
runnable examples, architecture overview, contributing, API reference,
changelog), updates content to match the current state of the project, and
then applies de-slopify rules for tone and concision. It iterates: find the
single biggest remaining improvement, apply it, repeat.

Framing rule: describe the project as it is, not "we added X" or "X is now Y."

## Import It

```toml
[imports.readme-revise]
source = "../packs/jeffrey/readme-revise"
```

## Attribution

Adapted from [Jeffrey Emanuel](https://github.com/Dicklesworthstone)
(@doodlestein)'s README Reviser.
