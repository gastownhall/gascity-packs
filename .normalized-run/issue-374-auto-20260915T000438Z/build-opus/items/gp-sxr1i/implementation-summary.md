---
schema: gc.build.implementation-summary.v1
workflow:
  id: gcg--9223372036854774672
  formula: do-work-item
methodology:
  pack: gascity
  name: build-basic
producer:
  formula: do-work-item
  stage: implement-item
  attempt: 1
status: approved
trace:
  upstream:
    - path: beads/gp-sxr1i
      hash: bead:gp-sxr1i
      ids:
        - AC-374-04
        - AC-374-06
        - AC-374-07
    - path: gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
      hash: git:4fb56420fdc48a5e447b2ca2331de92bd67ed420
    - path: gastown/formulas/mol-refinery-patrol.toml
      hash: git:2df2dca710ba79876f335300d9a37abbcb3d6d8b
    - path: scripts/gascity_pack_inference_gate.py
      hash: git:2df2dca710ba79876f335300d9a37abbcb3d6d8b
  coverage:
    - id: AC-374-04
      status: covered
    - id: AC-374-06
      status: covered
    - id: AC-374-07
      status: covered
---

# W3 — red control, verification sweep, and PR-body records

## Summary

Executes design verification steps 3 through 8 against the fixed tree
`2df2dca710ba79876f335300d9a37abbcb3d6d8b` and produces the PR-body records the
design requires to be written down rather than narrated.

The headline result: the identical test file, byte-unmodified, exits **1**
against the unguarded base and **0** against the fixed tree, with per-leg
outcomes matching the design's predicted table exactly. That is the evidence
that the guard is real and that the suite is not vacuous.

This item mutates no product code. Its deliverable is the verification and the
records artifact at
`.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/items/gp-sxr1i/pr-body.md`
(`sha256:9927ae7e63b12223dea3a8bc3481e4f2520b9040442d5202affbce1ef02adabc`).

## Intended Behavior

The red control uses the mechanism the design mandates and no substitute: a
detached worktree of the base
(`git worktree add --detach /tmp/rc-base-374 05031f2c`), with the fix tree's
test file aimed at it through `REBASE_GUARD_FORMULA`. The formula is never
hand-copied and the test is never edited between runs — the same file
(`sha256:e6ad1ae6…`) produced both runs, and only the environment variable
differed.

Outcomes are enumerated per leg rather than counted, which is why the suite
runs every leg and summarises verdicts instead of aborting at the first
failure. A first-failure abort could not produce the per-leg table in one run.

## Changed Files

| File | Change |
| --- | --- |
| *(none — product code untouched by construction)* | This item verifies and records; W1 and W2 carry the code. |

Verified tree: `2df2dca710ba79876f335300d9a37abbcb3d6d8b` on branch
`normalized/82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e/opus`.

## Verification

All measurements on `git version 2.43.0`.

First verification command — the red control against the unguarded base:

```
git worktree add --detach /tmp/rc-base-374 05031f2c66e080865c379ff799c7369430560a8f
REBASE_GUARD_FORMULA=/tmp/rc-base-374/gastown/formulas/mol-refinery-patrol.toml \
  bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
```

Result: exit 1. Enumerated per leg — legs 1, 1b, 4, 5 and 6 FAIL behaviourally;
leg 7 FAILS statically; legs 2, 3 and 8 stay green. This is the design's
predicted table with no deviation.

Final proof command — the identical file against the fixed tree:

```
bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
```

Result: exit 0, all nine legs PASS.

Supporting sweep, all green on the fixed tree:
`python3 -m pytest tests/test_gascity_pack_inference_gate.py -q` (89 passed);
the full CI loop `for t in gastown/tests/test_*.sh; do bash "$t"; done` (seven
files); TOML parse with all nine steps intact. Every pinned literal was grepped
and its sites enumerated in the records artifact, never counted, with all
`:NNN` re-derived on the fix branch. Leg 7 is green on the fixed tree and red on
the base tree, which is AC-374-07's static requirement.

The four step-8 records are written in full in `pr-body.md`: the no-errexit
execution assumption; the deliberately preserved bare checkout in the `1)` arm
and its asymmetry with the exit-checked `0)` arm; confirmation by enumeration
that no guard STOP arm pours a successor wisp (the wisp-pour sites are `:4`,
`:124`, `:276`, `:381`, `:486`, `:585`, `:1286`, of which only `:276` is in this
step, inside the halt); and the STOP respawn source.

| ID | Status |
| --- | --- |
| AC-374-04 | covered |
| AC-374-06 | covered |
| AC-374-07 | covered |

## Remaining Risks

**The STOP respawn source is verified from the pack contract, not from a live
rig.** This is the one place where the design asked for a production-rig
measurement and I could not take one: no city on the build host has a refinery
agent configured (`maintainer-city`, `orchestration`, `trust`, `platform`,
`gas-city-inc`, `substrate` — zero refinery agents, zero refinery sessions), so
there was no live refinery to observe. What the pack does establish is recorded
with citations, including a non-obvious consequence worth reviewer attention: a
guard STOP mutates no bead state, so it emits no `bead.updated` event and
therefore cannot self-trigger the refinery's event-watch wake path. The retry
rides on the reconciler's `on_demand` start, the refinery's next poll, or a
later external `gc session wake`. A single timed observation on a rig running
the gastown pack would settle it — force a guard STOP and record the delay
until the next refinery session and which source started it.

**Leg 3's rc carve-out is version-sensitive.** It asserts git's rebase-conflict
`rc 1`, measured here on git 2.43.0; CI runs git 2.52. Git documents only
"non-zero" on conflict. This is the single assertion in the suite that could
behave differently on the CI git, and it is deliberate and commented as such
because rc 1 is the discriminator the production step's prose already keys on.

**`tests/test_gastown_lint_findings.py` fails locally but is pre-existing.**
Confirmed by negative control: the same failure reproduces at base `05031f2c`
in a detached worktree with none of these changes (five pinned `pack.toml`
named-session waivers the local `gc` binary no longer reports). Unrelated to
this change.

The suite builds real git repositories per leg, so it is the slowest of the
gastown shell tests. It is well inside the CI step's budget, but it is the
first of these tests with that cost profile.
