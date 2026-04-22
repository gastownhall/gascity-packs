# Jeffrey Robot Mode Pack

Design an agent-friendly CLI for a project, via a Claude skill.

## What It Provides

- Skill overlay at `overlay/.claude/skills/robot-mode/SKILL.md`
- Invocable as `/robot-mode` in Claude

The skill guides a CLI redesign focused on machine consumers:

- `--json` on every command with stable key ordering
- TTY detection that flips to JSON automatically when stdout is piped
- Meaningful exit codes (`0` success, `1` not found, `2` invalid args,
  `3` permission denied, `4` conflict)
- Structured error bodies with code, message, and 1–2 corrected-example
  suggestions
- Dense, token-efficient output; help summaries under ~100 tokens
- Error tolerance that honors legible intent and teaches correct syntax

## Import It

```toml
[imports.robot-mode]
source = "../packs/jeffrey/robot-mode"
```

## Attribution

Adapted from [Jeffrey Emanuel](https://github.com/Dicklesworthstone)
(@doodlestein)'s Robot-Mode Maker and CLI Error Tolerance prompts.
