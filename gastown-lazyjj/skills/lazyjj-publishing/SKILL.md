---
name: lazyjj-publishing
description: Learn how to publish LazyJJ stacks with bookmarks, GitHub CLI, and remote sync.
category: development
allowed-tools: Bash
---

# LazyJJ Publishing

Use this skill for the create-pr, sync-remote, and GitHub integration
tutorials. It turns a finished stack into reviewable pull requests.

## Covers

- [Create a Pull Request](https://lazyjj.dev/tutorials/create-pr/)
- [Sync with Remote](https://lazyjj.dev/tutorials/sync-remote/)
- [GitHub Integration](https://lazyjj.dev/integrations/github/)

## Workflow

1. Bookmark the stack tail.
2. Push the bookmark to the remote.
3. Create stacked PRs in order with `gh pr create`.
4. Fetch remote changes and rebase local branches when needed.

## Core Commands

```bash
jj bookmark set lazyjj-publish -r @-
jj git push --bookmark lazyjj-publish
gh pr create --head lazyjj-publish --fill
jj git fetch
jj rebase -o main
gh pr list --head lazyjj-publish
```

## Notes

- LazyJJ publish flow is bookmark-first, not `jj spr`-first.
- The branch chain should stay readable after publishing.
- Push the bookmark that names the stack tail you want reviewed.
