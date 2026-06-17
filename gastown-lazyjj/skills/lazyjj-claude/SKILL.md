---
name: lazyjj-claude
description: Use LazyJJ with Claude-style workspace isolation and checkpointing.
category: development
allowed-tools: Bash
---

# LazyJJ Claude Integration

Use this skill for the Claude integration tutorial. It explains how to keep
AI-driven work isolated and checkpointed inside a LazyJJ stack.

## Covers

- [Claude Integration](https://lazyjj.dev/integrations/claude/)

## Workflow

1. Keep AI work inside an isolated workspace.
2. Use small checkpoints so the stack stays readable.
3. Prefer stack-aware commits over broad messy edits.
4. Push only the review-ready head.

## Core Commands

```bash
jj new -m "wip"
jj describe -m "checkpoint"
jj absorb
jj bookmark set lazyjj-ai -r @-
jj git push --bookmark lazyjj-ai
```

## Notes

- Isolation is the main benefit.
- Checkpoints matter more than large, hard-to-review commits.
