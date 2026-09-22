---
schema: gc.build.implementation-summary.v1
workflow:
  id: gcg--9223372036854775480
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
    - path: beads/gp-opi6t
      hash: bead:gp-opi6t
      ids:
        - AC-374-01
        - AC-374-02
        - AC-374-03
        - AC-374-05
        - AC-374-06
        - AC-374-07
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work-contract.json
      hash: sha256:04d51caeeb64a121224cab4ed2a331b11b17f864ae437041a684306e27ba9616
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/approved-design.md
      hash: sha256:057ad99d6da1db77b8fb68d5e7297b8d988eb7fffa697aea37d1638a32ce9738
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/decompose.md
      hash: sha256:84a9b1833164f4de4c61b8b700d73270a66fb1b5ec146e27ebc3fc58d1a26b5c
    - path: gastown/formulas/mol-refinery-patrol.toml
      hash: sha256:95ae370a8f1531c277a23e8c0a6e7c171e24902558228e4232e502f2cd3fb64d
    - path: scripts/gascity_pack_inference_gate.py
      hash: sha256:01220c0227e08eedc50b4f1a31e6efd55525487d1d79b72c5723cd69d4e2409e
  coverage:
    - id: AC-374-01
      status: covered
    - id: AC-374-02
      status: covered
    - id: AC-374-03
      status: covered
    - id: AC-374-05
      status: covered
    - id: AC-374-06
      status: covered
    - id: AC-374-07
      status: covered
---

# Implementation summary — issue-374 W2 (drain item 1, lane terra)

## Summary

Executed drain item 1 (member `gp-opi6t`, item root
`gcg--9223372036854775480`) of the terra implementation lane for run
`issue-374-auto-20260915T000438Z`: **W2 — D1+D2 formula insertion and
D3 inference-gate repin, atomic.**

Landed the guarded ancestry decision in
`gastown/formulas/mol-refinery-patrol.toml` step `rebase` and the five
new `GASTOWN_BUILD_WORKFLOW_CONTRACTS['mol-refinery-patrol']` fragments
in `scripts/gascity_pack_inference_gate.py` in **one commit**. The
approved design forbids splitting this item: never formula without
gate (AC-374-07). W1's test-first suite
(`83a2525e1a6956292144c1e82c1ba38b7a5e25c5`) was already on the
candidate branch; this commit sits on top of it.

All work ran inside the authoritative worktree
`/data/projects/gascity-packs/worktrees/normalized-b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141-terra`
after verifying `pwd -P` equals that path.

## Intended Behavior

Per `work/decompose.md` W2 and design sections D1, D2, and D3:

- **D1 insertion** between the halt's closing `fi` and the former
  unguarded checkout+rebase pair, order prune-fetch → halt →
  guard-fetch → probe → case. The prune fetch (`:252` on this tree,
  base `:248`) and the missing-target halt (`:253–:297` on this tree,
  base `:249–:293`) stay byte-identical to `05031f2c`.
- **Checked dual-refspec force-fetch** of `$BRANCH` and `$TARGET` with
  unbraced `$BRANCH` spelling (site-unique vs merge-push's braced
  `${BRANCH}`), failing closed: echo + `gc runtime drain-ack` +
  `exit 1`, no probe, no checkout, no rebase, no bead mutation.
- **Probe** `git merge-base --is-ancestor "origin/$TARGET" "origin/$BRANCH"`
  captured into `ANCESTOR_RC` (non-reserved; suffix-family distinct
  from merge-push `:850`'s `ANCESTOR_STATUS`). Three-way `case`:
  rc 0 = exit-checked skip-arm checkout + `SKIP-REBASE:` narration;
  rc 1 = today's bare `git checkout -b temp origin/$BRANCH` + unquoted
  `git rebase origin/$TARGET`; any other rc = STOP, never "not an
  ancestor".
- **D2 prose** (nothing removed): skip is a first-class success path;
  the conflict preamble now names already-based sources and
  fetch/probe errors as already ruled out; the intro rationale names
  the ancestry decision.
- **D3**: keep the existing `git rebase origin/$TARGET` pin; add the
  five fragments that can only be satisfied by the new block.

Untouched: merge-push from `id = "merge-push"` onward (byte-identical
to base, including the `:850` source→target already-merged gate), the
conflict-rejection numbered tail from `1. Abort:` onward, find-work,
and the witness suite.

## Changed Files

W2's deliverable is commit
`bb0c9de022cbc81dad012d509535d2feb766f251` on branch
`normalized/b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141/terra`.
`git show --stat --format= bb0c9de` lists exactly two files:

- `gastown/formulas/mol-refinery-patrol.toml` — D1 insertion + D2 prose
  (+59 / −2 in the rebase step only).
- `scripts/gascity_pack_inference_gate.py` — five added fragments at
  the `mol-refinery-patrol` command dict (`:122`).

No other path changed. Halt block, conflict tail, and everything from
`id = "merge-push"` onward hash-equal the base blob.

## Verification

Measured on `git version 2.43.0`. All commands ran after `pwd -P`
confirmed the authoritative worktree.

First verification command — W1's suite against this tree's formula
(observed pass, exit 0; all nine legs green, which is the guarded
profile the design predicts):

```console
$ cd /data/projects/gascity-packs/worktrees/normalized-b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141-terra
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

Diff confinement, re-derived on this tree against `05031f2c`: halt
(`git fetch --prune origin` through the halt's closing `fi`)
byte-identical; conflict tail from `1. Abort:` byte-identical;
`id = "merge-push"` through EOF byte-identical. Formula diff is the
D1 block plus the three D2 prose amendments only.

Pinned literals grepped at fix time (sites enumerated, never a
count). Each fragment appears in the gate dict and in the formula:

| Fragment | Formula site (this tree) | Gate site |
| --- | --- | --- |
| `git rebase origin/$TARGET` | `:332` (`1)` arm, unquoted) | `:124` |
| `git fetch origin "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"` | `:304` | `:125` |
| `git merge-base --is-ancestor "origin/$TARGET" "origin/$BRANCH"` | `:315` | `:126` |
| `ANCESTOR_RC=$?` | `:316` | `:127` |
| `cannot evaluate rebase ancestry. STOP. Do not mutate bead state.` | `:305` (fetch STOP) and `:337` (probe-error STOP) | `:128` |
| `echo "SKIP-REBASE:` | `:327` | `:129` |

The prose-dict tuple at `:91` (`metadata.branch`, `fast-forward merge`,
`run tests before merging`, `metadata.target`, `closes the bead`) is
untouched. The `setup_formulas` registry entry at `:795` names the
formula only and was not changed.

Final proof command — inference-gate pytest on the changed tree
(observed pass, exit 0, 89 passed). This environment's user site is
remapped, so the design's `python3 -m pytest …` was invoked with
`PYTHONPATH` pointing at the host user site that actually contains
pytest 9.0.3:

```console
$ PYTHONPATH=/home/ubuntu/.local/lib/python3.12/site-packages \
    python3 -m pytest tests/test_gascity_pack_inference_gate.py -q
........................................................................ [ 80%]
.................                                                        [100%]
89 passed in 3.24s
```

## Remaining Risks

- **W3 owns the red-control transcript** (`git worktree add --detach`
  at `05031f2c` plus `REBASE_GUARD_FORMULA`), the full
  `gastown/tests/test_*.sh` sweep, PR-body records (no-errexit
  assumption, `1)`-arm bare-checkout asymmetry, no-successor-wisp
  confirmation, verified STOP respawn source), and pin-site
  enumeration in a PR body. `push=false` / `open_pr=false` for this
  run — no PR exists here.
- **W4 files the residual-precision-(b) follow-up family**
  (deleted-`$BRANCH` park mirror + repeated stranded-`temp`
  checkout-STOP). Committed prose is not the tracking.
- **No-errexit execution assumption** (design residual): a probe rc=1
  must fall through to the `case`. Status quo at base `:295`; recorded
  here so W3 can put it in the PR body.
- **Deliberate `1)`-arm bare checkout** vs exit-checked `0)` arm: the
  rc=1-arm stranded-`temp` wedge is pre-existing and scoped out.
- **`BRANCH == TARGET` degeneracy** is asserted by design analysis
  only, exercised by no test leg — accepted.
- **Line citations in this summary are this-tree numbers** and must
  not be copied forward as if they were still `05031f2c` anchors.

| ID | Status |
| --- | --- |
| AC-374-01 | covered |
| AC-374-02 | covered |
| AC-374-03 | covered |
| AC-374-05 | covered |
| AC-374-06 | covered |
| AC-374-07 | covered |
