---
schema: gc.build.implementation-summary.v1
workflow:
  id: gcg--9223372036854775475
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
    - path: beads/gp-sc2pz
      hash: bead:gp-sc2pz
      ids:
        - AC-374-04
        - AC-374-06
        - AC-374-07
    - path: gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
      hash: sha256:45ff999a8e76ff58a2a055333b54c6bf5e699766bfd3a5b009a3eaa2b1efa307
    - path: gastown/formulas/mol-refinery-patrol.toml
      hash: sha256:95ae370a8f1531c277a23e8c0a6e7c171e24902558228e4232e502f2cd3fb64d
    - path: scripts/gascity_pack_inference_gate.py
      hash: sha256:01220c0227e08eedc50b4f1a31e6efd55525487d1d79b72c5723cd69d4e2409e
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work-contract.json
      hash: sha256:04d51caeeb64a121224cab4ed2a331b11b17f864ae437041a684306e27ba9616
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/approved-design.md
      hash: sha256:057ad99d6da1db77b8fb68d5e7297b8d988eb7fffa697aea37d1638a32ce9738
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/decompose.md
      hash: sha256:84a9b1833164f4de4c61b8b700d73270a66fb1b5ec146e27ebc3fc58d1a26b5c
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/terra/items/gp-sc2pz/pr-body.md
      hash: sha256:fdfb77ab3621628372fb24fb91aa269080fdd80526023f2a58d8e3f80e60e32f
  coverage:
    - id: AC-374-04
      status: covered
    - id: AC-374-06
      status: covered
    - id: AC-374-07
      status: covered
---

# Implementation summary — issue-374 W3 (drain item 2, lane terra)

## Summary

Executed drain item 2 (member `gp-sc2pz`, item root
`gcg--9223372036854775475`) of the terra implementation lane for run
`issue-374-auto-20260915T000438Z`: **W3 — red control, full verification
sweep, and PR-body records.**

This item mutates no product code. It runs design verification steps 3–8
against the tree W2 shipped (`bb0c9de022cbc81dad012d509535d2feb766f251`)
and writes the records the design requires to be written down rather
than narrated. The records artifact is
`.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/terra/items/gp-sc2pz/pr-body.md`
(`sha256:fdfb77ab3621628372fb24fb91aa269080fdd80526023f2a58d8e3f80e60e32f`).

The headline result: the identical test file, byte-unmodified, exits **1**
against the unguarded base and **0** against the fixed tree, with per-leg
outcomes matching the design's predicted table exactly.

All work ran inside the authoritative worktree
`/data/projects/gascity-packs/worktrees/normalized-b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141-terra`
after verifying `pwd -P` equals that path. Ownership:
`gc.drain_member_id=gp-sc2pz`, `gc.drain_index=2`, reserved convoy
`gp-jascc`, exclusive reservation `gcg--9223372036854774997`. Context
path hashes to `sha256:04d51caeeb64a121224cab4ed2a331b11b17f864ae437041a684306e27ba9616`.

## Intended Behavior

Per `work/decompose.md` W3 and design verification steps 3–8:

- Run the identical test file against the unguarded base via
  `git worktree add --detach <tmp> 05031f2c` plus `REBASE_GUARD_FORMULA`.
  Expected, enumerated per leg, never counted: legs 1, 1b, 4, 5, 6 fail
  behaviorally; leg 7 fails statically; legs 2, 3, 8 stay green.
- Then all nine green on the fixed tree.
- Record mechanism and git versions, the no-errexit assumption, the
  deliberate `1)`-arm bare-checkout asymmetry, the no-successor-wisp
  confirmation, and the verified STOP respawn source.
- Grep each pinned literal and enumerate sites in the PR body.
- Full `gastown/tests/test_*.sh` sweep and inference-gate pytest green.

Design verification step 9 (filing residual-precision-(b)) is **not** in
this item; W4 (`gp-2y2nd`) owns it.

## Changed Files

| File | Change |
| --- | --- |
| *(none — product code untouched by construction)* | This item verifies and records; W1 and W2 carry the code. |

Verified tree: `bb0c9de022cbc81dad012d509535d2feb766f251` on branch
`normalized/b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141/terra`.
Worktree remained clean (`git status --porcelain` empty) after the sweep.

Lane artifacts (outside the product tree):

- `work/builders/terra/items/gp-sc2pz/pr-body.md`
- `work/builders/terra/items/gp-sc2pz/evidence/stop-respawn-source.md`
- this summary

## Verification

Measured on `git version 2.43.0`. All commands ran after `pwd -P`
confirmed the authoritative worktree. Test file
`sha256:45ff999a8e76ff58a2a055333b54c6bf5e699766bfd3a5b009a3eaa2b1efa307`
was not edited between the red and green runs.

First verification command — red control against the unguarded base
(observed fail, exit 1; per-leg table matches the design):

```console
$ git worktree add --detach /tmp/rc-base-374-terra-w3 05031f2c66e080865c379ff799c7369430560a8f
$ REBASE_GUARD_FORMULA=/tmp/rc-base-374-terra-w3/gastown/formulas/mol-refinery-patrol.toml \
    bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
leg leg1: FAIL
leg leg1b: FAIL
leg leg2: PASS
leg leg3: PASS
leg leg4: FAIL
leg leg5: FAIL
leg leg6: FAIL
leg leg7: FAIL
leg leg8: PASS
FAIL: rebase-guard suite incomplete (see legs above)
```

Observed FAIL reasons, enumerated: leg1 artificial conflict (fence rc=1
on skip path); leg1b fence rc=0 with silent stranded-`temp` checkout
failure then rebase against detached HEAD; leg4 missing fetch-STOP
wording; leg5 missing-source rc=0 at checkout; leg6 missing probe-error
STOP wording; leg7 probe line occurs 0 times.

Final proof command — the identical file against the fixed tree
(observed pass, exit 0; all nine legs green):

```console
$ bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
leg leg1: PASS
leg leg1b: PASS
leg leg2: PASS
leg leg3: PASS
leg leg4: PASS
leg leg5: PASS
leg leg6: PASS
leg leg7: PASS
leg leg8: PASS
rebase-guard suite: all legs pass
```

Supporting sweep on the fixed tree, all green:

- `PYTHONPATH=/home/ubuntu/.local/lib/python3.12/site-packages python3 -m pytest tests/test_gascity_pack_inference_gate.py -q` — 89 passed in 3.39s
- `for t in gastown/tests/test_*.sh; do bash "$t"; done` — seven files, all pass (witness/heartbeat/polecat untouched)

Pinned literals grepped at fix time (sites enumerated, never a count).
Each fragment appears in the gate dict and in the formula; see
`pr-body.md`. Line citations are this-tree numbers.

Step-8 records (no-errexit, `1)`-arm asymmetry, no STOP-arm wisp, STOP
respawn source) are in `pr-body.md`. Respawn source measured against
this city's `[session_sleep] noninteractive = "5m"` plus the live order
table; this city has no live refinery session to time a STOP cycle.

| ID | Status |
| --- | --- |
| AC-374-04 | covered |
| AC-374-06 | covered |
| AC-374-07 | covered |

## Remaining Risks

- **W4 files the residual-precision-(b) follow-up family**
  (deleted-`$BRANCH` park mirror + repeated stranded-`temp`
  checkout-STOP). Committed prose is not the tracking. The PR-body
  placeholder is `<!-- W4 (gp-2y2nd) files that item and links it here. -->`.
- **STOP respawn was verified from live city config and the formula
  contract, not from a timed live-refinery STOP.** `maintainer-city`
  currently has no live refinery session. The 5-minute
  `noninteractive` policy, the absence of a refinery formula-order, and
  `orphan-sweep`/`nudge-on-route` being inert on a zero-mutation STOP
  are what this session could measure.
- **Leg 3's rc carve-out is version-sensitive.** It asserts git's
  rebase-conflict `rc 1`, measured here on git 2.43.0. Git documents only
  non-zero on conflict. CI git was not re-probed in this session.
- **No-errexit execution assumption** remains: a probe rc=1 must fall
  through to the `case`. Recorded in the PR body; not changed.
- **`push=false` / `open_pr=false`:** there is no GitHub PR in this run.
  The PR-body record is the lane artifact above.
- **Line citations in this summary are this-tree numbers** and must not
  be copied forward as if they were still `05031f2c` anchors.
