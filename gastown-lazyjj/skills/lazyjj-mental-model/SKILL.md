---
name: lazyjj-mental-model
description: Learn the JJ mental model, operation log, Git mappings, and common pitfalls.
category: development
allowed-tools: Bash
---

# LazyJJ Mental Model

Use this skill for the mental-model, operation-log, git-differences,
from-graphite, and common-mistakes tutorials. It is the "why this works"
skill for LazyJJ.

## Covers

- [Mental Model](https://lazyjj.dev/guides/mental-model/)
- [Operation Log](https://lazyjj.dev/guides/operation-log/)
- [Git Differences](https://lazyjj.dev/guides/git-differences/)
- [LazyJJ vs Graphite](https://lazyjj.dev/guides/from-graphite/)
- [Common Mistakes](https://lazyjj.dev/guides/common-mistakes/)

## Workflow

1. Teach that `@` is the current working-copy commit, not a staging area.
2. Explain that stacks are ancestry chains, not metadata files.
3. Show that `jj undo` and `jj op restore` are the safety net.
4. Map the old Git or Graphite habit to the LazyJJ equivalent.
5. Point out the most likely mistakes before the user makes them.

## Core Commands

```bash
jj log -r 'trunk()..@'
jj op log
jj undo
jj op restore <operation-id>
jj log -r 'stack & no_description'
```

## Notes

- Bookmarks do not auto-advance.
- Conflicts are recorded state, not a stop sign.
- Editing an old change rebases descendants automatically.
