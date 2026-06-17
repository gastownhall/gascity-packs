---
name: lazyjj-stack-workflow
description: Learn how to create, navigate, and edit LazyJJ stacks.
category: development
allowed-tools: Bash
---

# LazyJJ Stack Workflow

Use this skill for the create-stack, navigate-stack, and edit-mid-stack
tutorials. It is the "do the stack work" skill.

## Covers

- [Create a Stack](https://lazyjj.dev/tutorials/create-stack/)
- [Navigate Your Stack](https://lazyjj.dev/tutorials/navigate-stack/)
- [Edit Mid-Stack Commits](https://lazyjj.dev/tutorials/edit-mid-stack/)

## Workflow

1. Start from `trunk()` and create the first commit in the stack.
2. Move between stack entries with revsets instead of branch names.
3. Use `jj absorb` when a fix belongs in an earlier change.
4. Use `jj describe -m` to keep stack commits named as you work.

## Core Commands

```bash
jj git fetch
jj new trunk() -m "work: <short summary>"
jj log -r 'trunk()..@'
jj log -r 'stack & no_description'
jj absorb
jj diff --from branch_off
jj new -m "next"
jj describe -r @- -m "short description"
```

## Notes

- Keep checkpoints small.
- Prefer one focused change per stack layer.
- Rebase happens automatically when you rewrite history.
