---
name: lazyjj-foundations
description: Learn LazyJJ installation, the quick start, and the first working stack.
category: development
allowed-tools: Bash
---

# LazyJJ Foundations

Use this skill for the introduction, installation, and quickstart tutorials.
It is the best first stop when someone is new to LazyJJ or wants a minimal
path from a blank repo to a working stack.

## Covers

- [Introduction](https://lazyjj.dev/introduction/)
- [Installation](https://lazyjj.dev/installation/)
- [Quick Start](https://lazyjj.dev/quickstart/)

## Workflow

1. Confirm `jj` and `gh` are installed.
2. Install LazyJJ if the environment is not already configured.
3. Use the quick-start commands to create the first stack and bookmark.
4. Hand the user off to the stack workflow skill once they can read the log.

## Core Commands

```bash
curl -fsSL https://lazyjj.dev/install.sh | bash
jj log -r 'trunk()..@'
jj new main
jj commit -m "feat: first stack commit"
jj bookmark set lazyjj-demo -r @-
jj git push --bookmark lazyjj-demo
gh pr create --head lazyjj-demo --fill
```
