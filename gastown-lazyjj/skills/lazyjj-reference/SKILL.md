---
name: lazyjj-reference
description: Learn LazyJJ aliases, advanced revsets, and stack reference pages.
category: development
allowed-tools: Bash
---

# LazyJJ Reference

Use this skill for the aliases, advanced revsets, and stack reference pages.
It is the "look up the exact command" skill.

## Covers

- [Aliases](https://lazyjj.dev/reference/aliases/)
- [Advanced Revsets](https://lazyjj.dev/reference/revsets-advanced/)
- [Stack Reference](https://lazyjj.dev/reference/stack/)

## Workflow

1. Use aliases only when they are already available in the repo config.
2. Use advanced revsets to select exactly the stack slice you need.
3. Treat the stack reference as the canonical command map for the pack.

## Core Commands

```bash
jj log -r 'trunk()..@'
jj log -r 'stack & no_description'
jj help aliases
jj help revsets
```

## Notes

- Aliases should make the stack easier to inspect, not hide the graph.
- Revsets are the native way to talk about stack shape in jj.
