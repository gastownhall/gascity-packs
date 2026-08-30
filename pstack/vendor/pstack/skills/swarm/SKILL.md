---
name: swarm
description: "Fan out N parallel workers, drain them, and return one report. Use for /swarm, 'swarm this', or parallel coverage, races, gauntlets, and exploration."
disable-model-invocation: true
---

# Swarm

Fan out N parallel workers. They may cover separate slices, race the same brief, or mix both. The parent waits, aggregates, and returns one report.

## Start

Open a todolist with one entry per phase before launching anything.

1. Frame
2. Fan out
3. Aggregate
4. Report

## Phase A: Frame

1. State the done predicate and the artifact or report the swarm must return.
2. Choose the shape. Partition into slices, race N workers on identical briefs, or mix both. For a race or mixed shape, declare `first pass`, `rank all`, or `best-of` before spawning.
3. Set N from the user or derive it from the shape. N is total workers.
4. Pick the worker model from toml key `swarm-workers` per `../setup-pstack/references/resolve-model.md`. Absent file: send `grok-4.6` (omit if rejected). Missing key, `inherit-parent`, or `auto`: omit `model`. For a model race, name each arm from this session's detected slugs only.
5. Give each worker its own writable output when it writes. Use a worktree, branch, or `/tmp/swarm-<slug>/worker-<n>/`.

## Phase B: Fan out

Spawn all N workers in one parent turn with `spawn_subagent`: `subagent_type: "pstack:swarm-workers"` ([`../setup-pstack/references/resolve-effort.md`](../setup-pstack/references/resolve-effort.md)), `isolation: "worktree"`, `background: true`, and the configured `model`. Use `isolation: "none"` only when the worker needs this machine's cwd. Do not send `reasoning_effort`. Join with `get_command_or_subagent_output`.

Every brief stands alone. Include the goal, scope, exact slice or race arm, how to verify, and what to report. Reports use `PASS`, `ISSUES`, or `BLOCKED` with evidence.

If a worker drops out, proceed with N-1 and note it.

## Phase C: Aggregate

Read the terminal results. For coverage, every required slice needs a result. For a race, apply the selection rule declared up front. Use first pass, rank all, or best-of. Do not paste raw worker dumps.

Keep a compact result table, one-line evidenced issues, and explicit gaps or dropouts.

## Phase D: Report

Return one consolidated in-chat report with the table, issue one-liners, gaps or dropouts, and the race rule when used.
