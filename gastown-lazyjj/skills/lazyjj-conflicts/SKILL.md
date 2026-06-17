---
name: lazyjj-conflicts
description: Learn first-class conflict handling and conflict recovery in LazyJJ.
category: development
allowed-tools: Bash
---

# LazyJJ Conflicts

Use this skill for the resolve-conflicts tutorial. It is the "what to do when
the graph conflicts" skill.

## Covers

- [Resolve Conflicts](https://lazyjj.dev/tutorials/resolve-conflicts/)

## Workflow

1. Show that conflicts are normal jj state.
2. Resolve the file content directly.
3. Re-run the relevant jj command or checkpoint.
4. Use the operation log if the resolution went the wrong way.

## Core Commands

```bash
jj log -r 'trunk()..@'
jj op log
jj resolve
jj absorb
jj undo
```

## Notes

- Do not panic when conflict markers appear.
- Treat conflict resolution as part of normal stack editing.
- Syncing from remote is a common place to see conflicts.
