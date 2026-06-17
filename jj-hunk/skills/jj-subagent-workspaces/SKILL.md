---
name: jj-subagent-workspaces
description: Use when delegating a coding task to a subagent and you need an isolated working directory backed by jj. Covers picking a parent commit, creating a jj workspace, briefing the subagent on jj ground rules, integrating its commits back into the main stack, and cleaning up. Mechanism-agnostic — works for any subagent dispatch, including a plain shell `agent <prompt>` invocation.
---

# Jujutsu Workspaces for Subagent Isolation

## Overview

A **jj workspace** is a second working directory attached to the same `.jj/repo/` store. It has its own `@` (working-copy commit) and its own checkout on disk, but shares the commit graph, bookmarks, and operation log with every other workspace.

Workspaces are an excellent substrate for delegating work to a subagent:

- The subagent gets a real on-disk directory it can `cd` into and edit freely.
- Any commit it makes is **immediately visible** in the main workspace — no `pull`, `fetch`, `push`, or `merge` step.
- When the subagent finishes, the main agent can rebase, squash, or reorder the resulting commits into the user's stack with normal jj operations.
- Cleanup is two commands.

**Core principle:** the workspace is the subagent's sandbox; the commit graph is the shared output channel.

This skill covers only the jj side. **How** you spawn a subagent (shell exec, Task tool, API call, MCP, etc.) is intentionally out of scope — the workflow only requires that you can run the subagent with a chosen working directory.

## When to Use

- A task can be safely delegated to another agent and you don't want it editing the user's working copy.
- You want a subagent to run in parallel with your own edits in the main workspace.
- The task is bounded enough that it produces one or more commits you'll later land into the user's stack.
- You need a clean rollback path: bad output → abandon commits, forget workspace, delete directory.

Do **not** use a workspace if:

- The subagent only needs to read code. Just spawn it with the repo path; no isolation needed.
- The task is interactive (the subagent will need back-and-forth with the user mid-task — a workspace adds no value over the main one).
- You're on a colocated jj/git repo and the subagent needs git tooling. See [Colocated repos](#colocated-repos).

## Mental Model

jj workspaces are **not** git worktrees.

| | git worktree | jj workspace |
|---|---|---|
| Separate working directory | yes | yes |
| Separate refs / branches | yes | no — shared commit graph |
| Branch locking | yes | no — multiple workspaces can sit on the same commit |
| Merge-back step | yes | no — commits are already in the shared repo |
| Shared operation log | n/a | **yes** — `jj op restore` is dangerous across workspaces |
| Concurrent commands | risky | safe by design |

Think of each workspace as an independent cursor (`@`) into one repository. Commits, bookmarks, the op log, and conflicts are all shared.

## Workflow

```
1. Pick a parent commit for the subagent's work
2. Create the workspace at that parent
3. Brief the subagent (cwd + ground rules)
4. Spawn the subagent
5. Inspect the resulting commits from the main workspace
6. Integrate (rebase / squash / abandon) into the user's stack
7. Forget the workspace and delete the directory
```

### 1. Pick a parent

The subagent's commits will descend from this revision. Common choices:

```bash
jj log --no-pager -r 'trunk()'      # branch off trunk for a fresh feature
jj log --no-pager -r '@-'           # branch off the current parent
jj log --no-pager -r '<change>'     # branch off a specific change in the stack
```

The subagent will normally produce a linear stack starting from one parent.

### 2. Create the workspace

```bash
jj workspace add ../task-foo \
  --name task-foo \
  -r <parent-revset> \
  -m "subagent: <task summary>"
```

- `../task-foo` — directory on disk. Use a **sibling** path; do not nest inside the main workspace.
- `--name task-foo` — workspace name shown in `jj log` as `task-foo@`. Defaults to dest basename.
- `-r <parent>` — parents of the new `@`. Omit to share the main workspace's parent(s).
- `-m "..."` — description of the new (empty) `@`. Without `-m`, jj does not open an editor for a workspace's initial empty commit.
- `--sparse-patterns full` — pass this if the main workspace is sparse but the subagent needs the whole tree. Default `copy` inherits the main workspace's patterns.

Verify:

```bash
jj workspace list --no-pager
jj log --no-pager -r 'task-foo@ | task-foo@-'
```

### 3. Brief the subagent

The subagent's prompt needs, at minimum:

- **Working directory**: absolute path to the workspace.
- **VCS tool**: use `jj`, not `git`. If the `jj-surgeon` skill (or any jj reference) is available, point at it.
- **Commit discipline**: atomic commits with `jj commit -m "..."`. Leave `@` empty when done.
- **Scope**: stay inside the workspace directory. Do not touch other workspaces.
- **Forbidden ops**: no `jj op restore` (rewinds the **shared** op log across all workspaces). No `jj git push`. No bookmarks unless explicitly asked.
- **Deliverable**: print the change IDs of the resulting commits before exiting.

See the [prompt template](#subagent-prompt-template) below.

### 4. Spawn the subagent

Mechanism is up to you. The only requirement is that the subagent runs with the workspace directory as its working directory. Examples:

```bash
# Plain shell agent
( cd ../task-foo && agent-cli "$PROMPT" )

# Subprocess with explicit cwd
agent-cli --cwd ../task-foo "$PROMPT"

# Tool-based dispatch — set the tool's working-directory parameter
# Background process — capture output to a log file under ../task-foo/
```

This skill makes no assumption about the spawning API beyond that.

### 5. Inspect the result

From the main workspace:

```bash
jj log --no-pager -r 'task-foo@-::task-foo@'   # commits the subagent made
jj log --no-pager -r '<parent>::task-foo@'     # full stack since parent
jj show --git --no-pager task-foo@-            # diff of the most recent real commit
```

If the subagent followed the brief, its head is `task-foo@-` and `task-foo@` is empty. If it didn't:

- `task-foo@` still has uncommitted work — either commit it on its behalf with `jj commit -r task-foo@ -m "..."` (from inside the workspace) or abandon it.
- `task-foo@` has a description but is non-empty — same thing; it's still "being edited".

### 6. Integrate

Use normal jj history operations from the main workspace. Pick the one that fits the task:

```bash
# Append the subagent's stack to your current stack
jj rebase -s <first-subagent-change> -d @

# Insert into the middle of your stack
jj rebase -s <first-subagent-change> -A <change-in-stack>

# Collapse the subagent's work into one of your existing commits
jj squash --from <subagent-change> --into <target> -m "..."

# Discard everything
jj abandon <first-subagent-change>::<last-subagent-change>
```

All of these are safe across workspaces — the shared op log handles concurrency. Rewriting the subagent workspace's ancestors will mark `task-foo@` stale, which is fine if you're about to forget it. If you intend to keep the workspace alive for follow-up work, run `jj workspace update-stale` inside it before resuming.

### 7. Cleanup

```bash
jj workspace forget task-foo
rm -rf ../task-foo
```

`jj workspace forget` only drops the repo's tracking of that workspace — it does **not** delete files on disk. You must `rm -rf` separately. Order does not matter.

If the subagent left `task-foo@` non-empty and you don't want it:

```bash
jj abandon task-foo@
jj workspace forget task-foo
rm -rf ../task-foo
```

## Quick Reference

```bash
jj workspace add <path> -r <parent> --name <name> -m <msg>   # create
jj workspace list --no-pager                                  # list (use a template for scripting)
jj workspace forget <name>                                    # untrack (does NOT delete files)
jj workspace update-stale                                     # recover after ancestor rewrite
jj workspace rename <new-name>                                # rename current workspace

jj log --no-pager -r '<workspace-name>@'                      # see workspace's @
jj log --no-pager -r 'trunk()..<workspace-name>@'             # full stack
```

## Subagent prompt template

Adapt to your dispatch mechanism. The core pieces:

```
You are working inside a jj workspace at: <ABSOLUTE_PATH>
Set your working directory to that path and do not leave it.

Task: <USER-FACING TASK DESCRIPTION>

Ground rules:
- Use `jj` for all version control. Do NOT use `git`. If a `jj-surgeon`
  skill (or any jj reference) is available, follow it.
- Make atomic commits with `jj commit -m "..."` as you go. Leave `@`
  empty when you finish (`jj commit`, not `jj describe`).
- Do NOT touch other workspaces. Do NOT run `jj op restore` — the op
  log is shared across workspaces and that command rewinds all of
  them. Use `jj undo` or `jj op revert <op-id>` for targeted undo.
- Do NOT `jj git push`, do NOT create bookmarks, unless explicitly
  asked.

Done when:
- The task is complete and any tests pass.
- `jj status` shows a clean (empty) `@`.
- You have printed the resulting change IDs, e.g. via
  `jj log --no-pager -r 'trunk()..@-'`.
```

## Pitfalls

- **`forget` does not delete files; `rm -rf` does not forget.** Always pair them. A `rm -rf` without `forget` leaves a dangling workspace entry that jj will complain about.
- **`jj op restore` is repo-wide.** If the subagent runs it, every workspace rewinds, including the user's. Forbid it in the prompt. Use `jj op revert <op-id>` for targeted undo, or `jj --at-op=<op-id> restore -r @` for file-level recovery.
- **Stale working copies.** If you rebase the subagent's ancestors while it's still running, its next `jj` command will say "stale". Either avoid rewriting its ancestors mid-task, or have it run `jj workspace update-stale` before resuming.
- **Sparse-pattern inheritance.** `jj workspace add` copies sparse patterns by default. If the main workspace is sparse but the subagent needs the full tree, pass `--sparse-patterns full`.
- **Nesting.** Don't put the new workspace inside the main workspace's tree — the outer workspace will try to snapshot the inner `.jj/`. Use a sibling path.
- **Concurrent edits to the same commit.** Both workspaces can read the same commits, but if both rewrite the same change at once, one side ends up stale. Coordinate by giving the subagent a stack rooted at a parent you won't touch until it's done.
- **Empty-`@` discipline.** If the subagent uses `jj describe` instead of `jj commit`, its work stays in `task-foo@` (not `task-foo@-`). Your `rebase -s` reference will be off by one. Enforce `jj commit -m` in the prompt.
- **Workspace name vs. directory name.** `--name` controls the name used in jj (`name@`). Without it, the basename of the destination directory is used. Pick something memorable; you'll be typing it.

### Colocated repos

In a colocated jj/git repo, `jj workspace add` creates a directory with `.jj/` but typically without `.git/`. If the subagent's tooling needs git (editors, hooks, CI scripts), the workspace will not work for it. Options:

- Keep the subagent in the main workspace and use commit-level isolation instead (have it work on a side stack you'll abandon if it fails).
- Run the workflow on a non-colocated repo.

## Related skills

- `jj-surgeon` — comprehensive jj reference. Hand this to the subagent if it doesn't already know jj; in particular it covers safe operation-log handling, conflict resolution, and the hunk-level toolset.
- Subagent dispatch is intentionally mechanism-agnostic. Combine this skill with whatever spawning primitive your environment provides — shell exec, Task tool, API call, MCP, or other.
