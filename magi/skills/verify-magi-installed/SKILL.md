---
name: verify-magi-installed
description: Verify a magi target is fully installed by probing state.json plus closed bd beads; reject ambiguous or in-flight evidence
---

# verify-magi-installed

## What this skill verifies

A magi-deployed target (claude, codex, gemini, or openai) is installed and healthy on the current city. The skill consumes `state.json` plus the bd store; it does not read the deployed home directly.

## Evidence — accepted (all of)

a. `state.json` at `${GC_CITY_PATH}/.gc/runtime/packs/magi/state.json` exists, parses, and has `schema_version=4`.
b. `state.json` `installs.<target>.installed=true` for the queried target.
c. `state.json` `installs.<target>.last_run_rc == 0`.
d. `bd list --label pack:magi:install --status closed` returns at least one bead whose body references `installs.<target>.bead_id` from state.json.
e. `gc magi doctor` returns rc=0, or rc=2 with only warn-level checks (no rc=1 children).

## Evidence — rejected (any of disqualifies)

a. `state.json` is absent or unparseable.
b. `installs.<target>.last_run_rc != 0` and no later closed bead supersedes it.
c. `bd list --label pack:magi:install --status open` returns beads (an install is mid-flight or orphaned). Run `gc magi status` to reconcile, then re-verify.
d. `gc magi doctor` returns rc=1 (fail) on any check.
e. `inflight.json` is present at `${GC_CITY_PATH}/.gc/runtime/packs/magi/` (an install is mid-flight or crashed).
f. `installs.<target>.installed=true` but the deployed home directory is absent from disk.

## When ambiguous

The operator runs `gc magi status --json`. The skill consumes that JSON instead of reading `state.json` directly. The JSON output reconciles orphaned beads as its first action, so subsequent reads are consistent.

## Skill scope

This skill verifies install state only. It does not verify that the deployed runtime works (e.g. whether Claude or Codex can talk to LM Studio). For runtime health, run `gc magi doctor --target <name>` and inspect the `lmstudio`, `ssh`, and `launchd` checks.
