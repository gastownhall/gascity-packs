# Review context — issue-374 terra lane

Produced by `workflows-build-from-convoy.prepare-review` for the
inherited `build-from-review-base` suffix. Bookkeeping only: no code was
reviewed or changed by this step.

- Workflow root: `gcg--9223372036854775805`
- Implementation convoy: `gp-j5ugs`
- Artifact root: `/data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/terra`
- Aggregate implementation summary: `<artifact_root>/implementation-summary.md`
- Review repair policy: `once`
- Review mode: `agent`; interaction mode: `headless`; max iterations: `1`
- `push=false`, `open_pr=false` — there is no PR for this run.

## Implementation Worktrees

All four convoy items shared ONE worktree and ONE branch.

### Source anchor `gp-rtbrt` (W1), `gp-opi6t` (W2), `gp-sc2pz` (W3), `gp-2y2nd` (W4)

- Implementation worktree (absolute): `/data/projects/gascity-packs/worktrees/normalized-b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141-terra`
- Branch: `normalized/b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141/terra`
- Base revision: `05031f2c66e080865c379ff799c7369430560a8f`
- Head revision: `bb0c9de022cbc81dad012d509535d2feb766f251`
- Diff range: `05031f2c66e080865c379ff799c7369430560a8f..HEAD` (= `05031f2c66e080865c379ff799c7369430560a8f..bb0c9de022cbc81dad012d509535d2feb766f251`)
- Worktree status at prepare-review time: clean (no untracked or modified paths)

Commits in range:

```
bb0c9de fix(gastown): skip refinery rebase when target is already an ancestor (issue 374)
83a2525 test(gastown): regression suite for the refinery rebase ancestry guard (issue 374)
```

Changed files in range:

```
 gastown/formulas/mol-refinery-patrol.toml          |  63 ++-
 .../tests/test_mol_refinery_patrol_rebase_guard.sh | 622 +++++++++++++++++++++
 scripts/gascity_pack_inference_gate.py             |   5 +
 3 files changed, 686 insertions(+), 4 deletions(-)
```

```
M	gastown/formulas/mol-refinery-patrol.toml
A	gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
M	scripts/gascity_pack_inference_gate.py
```

### Proof commands (claimed by the items, not re-run here)

Run from the implementation worktree above:

```
bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
PYTHONPATH=/home/ubuntu/.local/lib/python3.12/site-packages python3 -m pytest tests/test_gascity_pack_inference_gate.py -q
```

W3 additionally claims a detached red-control worktree at the base
revision; see its records artifact below.

### Anchor → artifact map

| Item | Anchor | Item root | Artifacts |
| --- | --- | --- | --- |
| W1 | `gp-rtbrt` | — | no per-item file (overwritten at the shared aggregate path); evidence in the bead close reason, reproduced in the aggregate summary |
| W2 | `gp-opi6t` | `gcg--9223372036854775480` | `items/gp-opi6t/implementation-summary.md` |
| W3 | `gp-sc2pz` | `gcg--9223372036854775475` | `items/gp-sc2pz/implementation-summary.md`, `items/gp-sc2pz/pr-body.md`, `items/gp-sc2pz/evidence/stop-respawn-source.md` |
| W4 | `gp-2y2nd` | `gcg--9223372036854774630` | `items/gp-2y2nd/implementation-summary.md`, `items/gp-2y2nd/pr-body.md` |

All four source anchors are closed with `gc.work_outcome=shipped`.
W3 and W4 are evidence/tracking-only and produced no commit by design.

Ignore `work/healed-20260921T1930Z/` and `work/healed-20260922T0130Z/`
for this lane: those are superseded generations, one of which is an
abandoned inverted child. The authoritative evidence is the `items/`
tree above.

## Appendix — `items/gp-opi6t/implementation-summary.md`

sha256: fa6b9c8c9a5bfda391178399f1bc2c3d8227ed9c6c037e90df151bf674c04447

````markdown
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
````

## Appendix — `items/gp-sc2pz/implementation-summary.md`

sha256: 75da1e148e1c0166f831f163658d396fb20859534f4e4b7a4a0a112b96c2297e

````markdown
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
````

## Appendix — `items/gp-2y2nd/implementation-summary.md`

sha256: 4c9776be156e6045d2eacc512b984134ffa824629d4f5a94545a3477cbf831b9

````markdown
---
schema: gc.build.implementation-summary.v1
workflow:
  id: gcg--9223372036854774630
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
    - path: beads/gp-2y2nd
      hash: bead:gp-2y2nd
      ids:
        - AC-374-06
    - path: beads/gp-kwysx
      hash: bead:gp-kwysx
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work-contract.json
      hash: sha256:04d51caeeb64a121224cab4ed2a331b11b17f864ae437041a684306e27ba9616
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/approved-design.md
      hash: sha256:057ad99d6da1db77b8fb68d5e7297b8d988eb7fffa697aea37d1638a32ce9738
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/decompose.md
      hash: sha256:84a9b1833164f4de4c61b8b700d73270a66fb1b5ec146e27ebc3fc58d1a26b5c
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/terra/items/gp-sc2pz/pr-body.md
      hash: sha256:fdfb77ab3621628372fb24fb91aa269080fdd80526023f2a58d8e3f80e60e32f
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/terra/items/gp-2y2nd/pr-body.md
      hash: sha256:c00e87b0937f1c9365aa3c3930ba2431162ffc73073fad0625e86aa0ebdbeda5
  coverage:
    - id: AC-374-06
      status: covered
---

# Implementation summary — issue-374 W4 (drain item 3, lane terra)

## Summary

Executed drain item 3 (member `gp-2y2nd`, item root
`gcg--9223372036854774630`) of the terra implementation lane for run
`issue-374-auto-20260915T000438Z`: **W4 — file the residual-precision-(b)
follow-up family as tracked work.**

This item mutates no product code. It discharges design verification
step 9: the residual-precision-(b) family is **filed** as tracked work
with a stable identifier and linked from the PR body. Committed prose
is not the tracking.

The tracked item is **`gp-kwysx`** — open, P2, assigned to `human`, one
family rather than two tickets: deleted-`$BRANCH` park mirror of the
missing-`$TARGET` halt, plus repeated stranded-`temp` checkout-STOP.

W3's sealed PR body is unchanged
(`sha256:fdfb77ab3621628372fb24fb91aa269080fdd80526023f2a58d8e3f80e60e32f`).
The linked copy is
`work/builders/terra/items/gp-2y2nd/pr-body.md`
(`sha256:c00e87b0937f1c9365aa3c3930ba2431162ffc73073fad0625e86aa0ebdbeda5`).

All inspection ran inside the authoritative worktree
`/data/projects/gascity-packs/worktrees/normalized-b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141-terra`
after verifying `pwd -P`. Ownership:
`gc.drain_member_id=gp-2y2nd`, `gc.drain_index=3`, reserved convoy
`gp-rfi3n`, exclusive reservation `gcg--9223372036854774997`.

## Intended Behavior

Per `work/decompose.md` W4 and design verification step 9:

- File the residual-precision-(b) family as a tracked work item with a
  stable identifier.
- Link that identifier from the PR body.
- Implement neither mirror, widen no STOP semantics, and do not touch
  merge-push.
- Keep the family as one ticket: both members are the same assigned
  head-of-line class.

AC-374-06 is carried by derivation: the design records this family under
STOP-routing residuals (guard composition and error routing).

## Changed Files

| File | Change |
| --- | --- |
| *(none — product code untouched by construction)* | Tracking only. Tree stayed at `bb0c9de022cbc81dad012d509535d2feb766f251`. |

Lane artifacts (outside the product tree):

- `work/builders/terra/items/gp-2y2nd/pr-body.md` — W3 body with the
  W4 placeholder replaced by the `gp-kwysx` link and inherited
  constraints
- this summary

Beads: created `gp-kwysx` (left open). Did not close `gp-kwysx`.

## Verification

First verification command — the tracked item exists and is open
(observed pass):

```console
$ gc bd show gp-kwysx --json
id gp-kwysx
status open
type task
priority 2
assignee human
title mol-refinery-patrol: assigned head-of-line family — deleted-$BRANCH park mirror + repeated stranded-temp checkout-STOP (issue 374 follow-up)
routed human
```

Final proof command — the PR body links the same id, and W3's sealed
body is unmodified (observed pass):

```console
$ rg -n 'gp-kwysx' work/builders/terra/items/gp-2y2nd/pr-body.md
226:**Tracked item: [`gp-kwysx`](beads/gp-kwysx)** — *mol-refinery-patrol:

$ sha256sum work/builders/terra/items/gp-sc2pz/pr-body.md
fdfb77ab3621628372fb24fb91aa269080fdd80526023f2a58d8e3f80e60e32f

$ git -C "$WORKTREE" status --porcelain
# empty
$ git -C "$WORKTREE" rev-parse HEAD
bb0c9de022cbc81dad012d509535d2feb766f251
```

No product tests: this item has no behavioral half by construction.

| ID | Status |
| --- | --- |
| AC-374-06 | covered |

## Remaining Risks

- **`gp-kwysx` is tracking, not an implementation.** Until that family
  lands, a permanently-deleted `$BRANCH` and a repeated stranded-`temp`
  still accumulate an assigned STOP. That is the accepted residual the
  design asked to track, not to fix here.
- **W3 PR-body digest is the pre-link one**, by design. Reviewers must
  read `items/gp-2y2nd/pr-body.md` for the link, not W3's sealed copy.
- **`push=false` / `open_pr=false`:** there is no GitHub PR in this run.
  The link lives in the lane artifact.
- **No-conflict-routing and no-halt-weakening constraints** are recorded
  on `gp-kwysx` and in the W4 PR body; they are not machine-enforced.
````

## Appendix — `items/gp-sc2pz/pr-body.md`

sha256: fdfb77ab3621628372fb24fb91aa269080fdd80526023f2a58d8e3f80e60e32f

````markdown
# fix(gastown/refinery): skip the rebase when the source is already based

Fixes #374.

`mol-refinery-patrol`'s `rebase` step used to check out `origin/$BRANCH` onto
`temp` and then run `git rebase origin/$TARGET` unconditionally. When
`origin/$TARGET` is already an ancestor of `origin/$BRANCH`, that rebase is
not a no-op: it flattens merge commits and drops the conflict resolutions
recorded in them.

Both failure modes were reproduced on `git version 2.43.0` while building
the fixtures, not inferred:

- **Merge-conflicting history (EX-1)** — linear replay hits an artificial
  conflict on an unchanged SHA (the rejection treadmill).
- **Clean history (EX-2)** — rebase succeeds but silently flattens; merge-push
  then force-pushes the rewrite over the source branch.

This lane's commits:

| Commit | Item |
| --- | --- |
| `83a2525e1a6956292144c1e82c1ba38b7a5e25c5` | W1 — regression suite (test-first) |
| `bb0c9de022cbc81dad012d509535d2feb766f251` | W2 — D1 guard + D2 prose + D3 gate repin, atomic |

The only permitted split is test-first, then formula-and-gate in one commit.
Shipping the formula without the gate repin in the same change violates
AC-374-07.

`push=false` / `open_pr=false` for this run: this file is the PR-body
record the design requires, not a GitHub pull request.

## The guard

Ordering is prune-fetch → halt → guard-fetch → probe → case. Every edge is
load-bearing:

- The explicit fetch **must follow** the missing-target halt. An explicit
  refspec fetch of a missing `$TARGET` exits 128, so running it first would
  swallow `target_branch_missing` into the generic STOP and skip the halt's
  park / escalation / wisp-pour.
- The fetch exit is **checked**. A failed fetch leaves stale tracking refs
  that can still satisfy `--is-ancestor`.
- The probe is captured bare into `ANCESTOR_RC` with `$?` on the next line
  (not `status`; zsh read-only), then discriminated three ways: rc 0 skips,
  rc 1 runs today's two lines, any other rc STOPs.
- The skip arm's checkout is **itself exit-checked**. The `1)` arm keeps
  today's bare `git checkout -b temp origin/$BRANCH`.

Every new STOP route is retry-later: echo, `gc runtime drain-ack`, `exit 1`.
No `rejection_reason`, no delete/reopen-source, no polecat reroute, no bead
mutation. Only the missing-`$TARGET` halt parks.

## Verification

All measurements on `git version 2.43.0`, inside worktree
`/data/projects/gascity-packs/worktrees/normalized-b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141-terra`
at `bb0c9de022cbc81dad012d509535d2feb766f251`. `pwd -P` matched before any
source read, test, or hash.

### Red control (design step 4)

Mechanism, exactly as specified — the fix tree's test file is invoked
byte-unmodified against a detached worktree of the unguarded base; the
formula is never hand-copied and the test is never edited between runs:

```
git worktree add --detach /tmp/rc-base-374-terra-w3 05031f2c66e080865c379ff799c7369430560a8f
REBASE_GUARD_FORMULA=/tmp/rc-base-374-terra-w3/gastown/formulas/mol-refinery-patrol.toml \
  bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
```

Test file `sha256:45ff999a8e76ff58a2a055333b54c6bf5e699766bfd3a5b009a3eaa2b1efa307`,
identical across both runs. Unguarded formula
`sha256:c5a2da6391b1cb2c20334322e892bb5a95873d145f319c7946347a3816e0f1d8`
at `05031f2c`. Fixed formula
`sha256:95ae370a8f1531c277a23e8c0a6e7c171e24902558228e4232e502f2cd3fb64d`
at `bb0c9de`.

Outcomes enumerated per leg, never counted (unguarded, exit 1):

| Leg | Result | Why |
| --- | --- | --- |
| 1 | FAIL | fence rc=1 on EX-1 skip path (artificial conflict) |
| 1b | FAIL | fence rc=0; stranded `temp` checkout failed silently, then rebase ran against detached HEAD |
| 2 | PASS | diverged clean still rebases |
| 3 | PASS | diverged conflicting still rc=1 with rebase in progress |
| 4 | FAIL | missing fetch-STOP wording; stale-ref trap still reaches rebase |
| 5 | FAIL | missing source surfaces at checkout with rc=0, not a STOP |
| 6 | FAIL | missing probe-error STOP wording |
| 7 | FAIL | probe line occurs 0 times (static; strings absent at `05031f2c`) |
| 8 | PASS | missing-target halt still fires |

Then the identical file against the fixed tree (no `REBASE_GUARD_FORMULA`):

```
bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
```

exit 0; legs 1, 1b, 2, 3, 4, 5, 6, 7, 8 all PASS.

### Inference gate (design step 5)

```
PYTHONPATH=/home/ubuntu/.local/lib/python3.12/site-packages \
  python3 -m pytest tests/test_gascity_pack_inference_gate.py -q
```

89 passed in 3.39s, exit 0. (This environment's user site is remapped, so
`python3 -m pytest` needs that `PYTHONPATH`.)

### Full gastown shell suite (design step 6)

```
for t in gastown/tests/test_*.sh; do bash "$t"; done
```

All seven files green: pack assets, theme scripts, rebase-guard, witness
orphan recovery, polecat churn watcher, polecat push gate, witness heartbeat.

### Pinned literals (design step 7)

Sites enumerated at fix time against this tree; never asserted as a count.

| Fragment | Formula site(s) | Gate site |
| --- | --- | --- |
| `git rebase origin/$TARGET` | `:332` (`1)` arm, unquoted) | `:124` |
| `git fetch origin "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"` | `:304` | `:125` |
| `git merge-base --is-ancestor "origin/$TARGET" "origin/$BRANCH"` | `:315` | `:126` |
| `ANCESTOR_RC=$?` | `:316` | `:127` |
| `cannot evaluate rebase ancestry. STOP. Do not mutate bead state.` | `:305` (fetch STOP) and `:337` (probe-error STOP) | `:128` |
| `echo "SKIP-REBASE:` | `:327` | `:129` |

`mol-refinery-patrol` also appears in the gate file at `:91` (prose dict:
`metadata.branch`, `fast-forward merge`, `run tests before merging`,
`metadata.target`, `closes the bead`) and `:795` (`setup_formulas` registry,
name only). Neither was changed.

## Step-8 records

### No-errexit execution assumption

The lifted fence captures `git merge-base --is-ancestor …` then
`ANCESTOR_RC=$?` and `case`s on it. A probe rc=1 **must** fall through to
the `case`. That is the same assumption base `:295` already depends on:
the recipe runs in a plain agent shell, not under `set -e`. Any future
errexit adaptation must use
`ANCESTOR_RC=0; git merge-base … || ANCESTOR_RC=$?` — never `|| true`,
which destroys the trichotomy.

### Deliberate `1)`-arm bare checkout

The `0)` arm is exit-checked (`if ! git checkout -b temp origin/$BRANCH;
then …` at `:322`). The `1)` arm keeps today's exact bare pair at
`:331-:332`. The rc=1-arm stranded-`temp` wedge is pre-existing and
scoped out of this change; recording it here so it is never read as an
oversight. The lift sentinel substring survives at both sites.

### No successor wisp on STOP arms

`gc bd mol wisp mol-refinery-patrol` sites in this formula, enumerated:
`:4`, `:124`, `:277`, `:383`, `:488`, `:587`, `:1288`.

Inside step `rebase` (`:223-:407`) the pours are `:277` (missing-`$TARGET`
halt, `:253-:297`) and `:383` (conflict-rejection tail). The guard block
`:298-:341` contains none: each STOP is echo + `gc runtime drain-ack` +
`exit 1` (`:305-:307` fetch, `:323-:325` skip-arm checkout, `:337-:339`
probe error). Line-scoped inspection of `:298-:341` finds no `bd update`
and no wisp. The halt alone pours, so one bead cannot end the merge lane;
a guard STOP deliberately can.

### Verified STOP respawn source (residual precision (a))

Measured 2026-09-22 against live `maintainer-city` (this pack's city),
replacing the design's repo-evidence-only assertion.

**Finding: the respawn source is the city-level `[session_sleep]` restart
policy applied by the session reconciler — not a poured wisp, not a
cron/order cadence, and not `orphan-sweep`.**

Resolved city config:

```
[session_sleep]
interactive_resume = "5m"
interactive_fresh  = "5m"
noninteractive     = "5m"
```

Pack-shipped `gastown/agents/refinery/agent.toml`: `wake_mode = "fresh"`,
`idle_timeout = "2h"`, `max_active_sessions = 1`. A patrol session is
non-interactive, so the reconciler restarts it on the `noninteractive =
"5m"` sleep policy. `find-work` already names the mechanism (`:217`):
"The session_sleep policy will restart this session after the configured
idle interval." The restarted session re-selects open beads assigned to
this refinery that carry `metadata.branch`.

Ruled out, each with the check:

1. **Not a poured wisp.** Guard STOP arms are echo + drain-ack + exit 1.
   The only rebase-step pour is the halt at `:277`.
2. **Not a cron/order cadence.** `gc order list` in this city has exactly
   three `formula`-type cooldown orders — `randy-patrol` (3h),
   `seth-patrol` (15m), `wendy-patrol` (1h) — and none for the refinery.
3. **Not `orphan-sweep`.** Core order, exec, 5m, "Reset beads assigned to
   dead agents back to the work pool". `is_known_agent`'s first real test
   is `agent_exists "$name"` against configured agent templates. A
   `<rig>/refinery` assignee is a configured agent, so a dead *session* of
   a live *agent* is not in scope. Header prose: beads "assigned to agents
   that don't exist in ANY rig".
4. **Not `nudge-on-route`.** Event trigger `bead.updated`. Guard STOP arms
   mutate no bead state, so no event fires. The zero-mutation contract is
   exactly what makes this recovery path inert.

This city currently has no live refinery session to time a STOP→respawn
cycle against; the mechanism is read off the live city config, the live
order table, and the formula's own find-work prose. Each restart re-runs
the decision from scratch against freshly fetched refs. A persistent
failure surfaces as a repeated STOP log rather than a mutation loop.

## Residual-precision-(b) follow-up

The residual-precision-(b) family — a deleted-`$BRANCH` park mirror of the
missing-`$TARGET` halt, plus repeated stranded-`temp` checkout-STOP — is
**not** filed here. Design verification step 9 belongs to W4
(`gp-2y2nd`). Committed prose is not the tracking.

<!-- W4 (gp-2y2nd) files that item and links it here. -->
````

## Appendix — `items/gp-2y2nd/pr-body.md`

sha256: c00e87b0937f1c9365aa3c3930ba2431162ffc73073fad0625e86aa0ebdbeda5

````markdown
# fix(gastown/refinery): skip the rebase when the source is already based

Fixes #374.

`mol-refinery-patrol`'s `rebase` step used to check out `origin/$BRANCH` onto
`temp` and then run `git rebase origin/$TARGET` unconditionally. When
`origin/$TARGET` is already an ancestor of `origin/$BRANCH`, that rebase is
not a no-op: it flattens merge commits and drops the conflict resolutions
recorded in them.

Both failure modes were reproduced on `git version 2.43.0` while building
the fixtures, not inferred:

- **Merge-conflicting history (EX-1)** — linear replay hits an artificial
  conflict on an unchanged SHA (the rejection treadmill).
- **Clean history (EX-2)** — rebase succeeds but silently flattens; merge-push
  then force-pushes the rewrite over the source branch.

This lane's commits:

| Commit | Item |
| --- | --- |
| `83a2525e1a6956292144c1e82c1ba38b7a5e25c5` | W1 — regression suite (test-first) |
| `bb0c9de022cbc81dad012d509535d2feb766f251` | W2 — D1 guard + D2 prose + D3 gate repin, atomic |

The only permitted split is test-first, then formula-and-gate in one commit.
Shipping the formula without the gate repin in the same change violates
AC-374-07.

`push=false` / `open_pr=false` for this run: this file is the PR-body
record the design requires, not a GitHub pull request.

## The guard

Ordering is prune-fetch → halt → guard-fetch → probe → case. Every edge is
load-bearing:

- The explicit fetch **must follow** the missing-target halt. An explicit
  refspec fetch of a missing `$TARGET` exits 128, so running it first would
  swallow `target_branch_missing` into the generic STOP and skip the halt's
  park / escalation / wisp-pour.
- The fetch exit is **checked**. A failed fetch leaves stale tracking refs
  that can still satisfy `--is-ancestor`.
- The probe is captured bare into `ANCESTOR_RC` with `$?` on the next line
  (not `status`; zsh read-only), then discriminated three ways: rc 0 skips,
  rc 1 runs today's two lines, any other rc STOPs.
- The skip arm's checkout is **itself exit-checked**. The `1)` arm keeps
  today's bare `git checkout -b temp origin/$BRANCH`.

Every new STOP route is retry-later: echo, `gc runtime drain-ack`, `exit 1`.
No `rejection_reason`, no delete/reopen-source, no polecat reroute, no bead
mutation. Only the missing-`$TARGET` halt parks.

## Verification

All measurements on `git version 2.43.0`, inside worktree
`/data/projects/gascity-packs/worktrees/normalized-b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141-terra`
at `bb0c9de022cbc81dad012d509535d2feb766f251`. `pwd -P` matched before any
source read, test, or hash.

### Red control (design step 4)

Mechanism, exactly as specified — the fix tree's test file is invoked
byte-unmodified against a detached worktree of the unguarded base; the
formula is never hand-copied and the test is never edited between runs:

```
git worktree add --detach /tmp/rc-base-374-terra-w3 05031f2c66e080865c379ff799c7369430560a8f
REBASE_GUARD_FORMULA=/tmp/rc-base-374-terra-w3/gastown/formulas/mol-refinery-patrol.toml \
  bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
```

Test file `sha256:45ff999a8e76ff58a2a055333b54c6bf5e699766bfd3a5b009a3eaa2b1efa307`,
identical across both runs. Unguarded formula
`sha256:c5a2da6391b1cb2c20334322e892bb5a95873d145f319c7946347a3816e0f1d8`
at `05031f2c`. Fixed formula
`sha256:95ae370a8f1531c277a23e8c0a6e7c171e24902558228e4232e502f2cd3fb64d`
at `bb0c9de`.

Outcomes enumerated per leg, never counted (unguarded, exit 1):

| Leg | Result | Why |
| --- | --- | --- |
| 1 | FAIL | fence rc=1 on EX-1 skip path (artificial conflict) |
| 1b | FAIL | fence rc=0; stranded `temp` checkout failed silently, then rebase ran against detached HEAD |
| 2 | PASS | diverged clean still rebases |
| 3 | PASS | diverged conflicting still rc=1 with rebase in progress |
| 4 | FAIL | missing fetch-STOP wording; stale-ref trap still reaches rebase |
| 5 | FAIL | missing source surfaces at checkout with rc=0, not a STOP |
| 6 | FAIL | missing probe-error STOP wording |
| 7 | FAIL | probe line occurs 0 times (static; strings absent at `05031f2c`) |
| 8 | PASS | missing-target halt still fires |

Then the identical file against the fixed tree (no `REBASE_GUARD_FORMULA`):

```
bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
```

exit 0; legs 1, 1b, 2, 3, 4, 5, 6, 7, 8 all PASS.

### Inference gate (design step 5)

```
PYTHONPATH=/home/ubuntu/.local/lib/python3.12/site-packages \
  python3 -m pytest tests/test_gascity_pack_inference_gate.py -q
```

89 passed in 3.39s, exit 0. (This environment's user site is remapped, so
`python3 -m pytest` needs that `PYTHONPATH`.)

### Full gastown shell suite (design step 6)

```
for t in gastown/tests/test_*.sh; do bash "$t"; done
```

All seven files green: pack assets, theme scripts, rebase-guard, witness
orphan recovery, polecat churn watcher, polecat push gate, witness heartbeat.

### Pinned literals (design step 7)

Sites enumerated at fix time against this tree; never asserted as a count.

| Fragment | Formula site(s) | Gate site |
| --- | --- | --- |
| `git rebase origin/$TARGET` | `:332` (`1)` arm, unquoted) | `:124` |
| `git fetch origin "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"` | `:304` | `:125` |
| `git merge-base --is-ancestor "origin/$TARGET" "origin/$BRANCH"` | `:315` | `:126` |
| `ANCESTOR_RC=$?` | `:316` | `:127` |
| `cannot evaluate rebase ancestry. STOP. Do not mutate bead state.` | `:305` (fetch STOP) and `:337` (probe-error STOP) | `:128` |
| `echo "SKIP-REBASE:` | `:327` | `:129` |

`mol-refinery-patrol` also appears in the gate file at `:91` (prose dict:
`metadata.branch`, `fast-forward merge`, `run tests before merging`,
`metadata.target`, `closes the bead`) and `:795` (`setup_formulas` registry,
name only). Neither was changed.

## Step-8 records

### No-errexit execution assumption

The lifted fence captures `git merge-base --is-ancestor …` then
`ANCESTOR_RC=$?` and `case`s on it. A probe rc=1 **must** fall through to
the `case`. That is the same assumption base `:295` already depends on:
the recipe runs in a plain agent shell, not under `set -e`. Any future
errexit adaptation must use
`ANCESTOR_RC=0; git merge-base … || ANCESTOR_RC=$?` — never `|| true`,
which destroys the trichotomy.

### Deliberate `1)`-arm bare checkout

The `0)` arm is exit-checked (`if ! git checkout -b temp origin/$BRANCH;
then …` at `:322`). The `1)` arm keeps today's exact bare pair at
`:331-:332`. The rc=1-arm stranded-`temp` wedge is pre-existing and
scoped out of this change; recording it here so it is never read as an
oversight. The lift sentinel substring survives at both sites.

### No successor wisp on STOP arms

`gc bd mol wisp mol-refinery-patrol` sites in this formula, enumerated:
`:4`, `:124`, `:277`, `:383`, `:488`, `:587`, `:1288`.

Inside step `rebase` (`:223-:407`) the pours are `:277` (missing-`$TARGET`
halt, `:253-:297`) and `:383` (conflict-rejection tail). The guard block
`:298-:341` contains none: each STOP is echo + `gc runtime drain-ack` +
`exit 1` (`:305-:307` fetch, `:323-:325` skip-arm checkout, `:337-:339`
probe error). Line-scoped inspection of `:298-:341` finds no `bd update`
and no wisp. The halt alone pours, so one bead cannot end the merge lane;
a guard STOP deliberately can.

### Verified STOP respawn source (residual precision (a))

Measured 2026-09-22 against live `maintainer-city` (this pack's city),
replacing the design's repo-evidence-only assertion.

**Finding: the respawn source is the city-level `[session_sleep]` restart
policy applied by the session reconciler — not a poured wisp, not a
cron/order cadence, and not `orphan-sweep`.**

Resolved city config:

```
[session_sleep]
interactive_resume = "5m"
interactive_fresh  = "5m"
noninteractive     = "5m"
```

Pack-shipped `gastown/agents/refinery/agent.toml`: `wake_mode = "fresh"`,
`idle_timeout = "2h"`, `max_active_sessions = 1`. A patrol session is
non-interactive, so the reconciler restarts it on the `noninteractive =
"5m"` sleep policy. `find-work` already names the mechanism (`:217`):
"The session_sleep policy will restart this session after the configured
idle interval." The restarted session re-selects open beads assigned to
this refinery that carry `metadata.branch`.

Ruled out, each with the check:

1. **Not a poured wisp.** Guard STOP arms are echo + drain-ack + exit 1.
   The only rebase-step pour is the halt at `:277`.
2. **Not a cron/order cadence.** `gc order list` in this city has exactly
   three `formula`-type cooldown orders — `randy-patrol` (3h),
   `seth-patrol` (15m), `wendy-patrol` (1h) — and none for the refinery.
3. **Not `orphan-sweep`.** Core order, exec, 5m, "Reset beads assigned to
   dead agents back to the work pool". `is_known_agent`'s first real test
   is `agent_exists "$name"` against configured agent templates. A
   `<rig>/refinery` assignee is a configured agent, so a dead *session* of
   a live *agent* is not in scope. Header prose: beads "assigned to agents
   that don't exist in ANY rig".
4. **Not `nudge-on-route`.** Event trigger `bead.updated`. Guard STOP arms
   mutate no bead state, so no event fires. The zero-mutation contract is
   exactly what makes this recovery path inert.

This city currently has no live refinery session to time a STOP→respawn
cycle against; the mechanism is read off the live city config, the live
order table, and the formula's own find-work prose. Each restart re-runs
the decision from scratch against freshly fetched refs. A persistent
failure surfaces as a repeated STOP log rather than a mutation loop.

## Residual-precision-(b) follow-up

Filed as tracked work (design verification step 9). Committed prose is
not the tracking.

**Tracked item: [`gp-kwysx`](beads/gp-kwysx)** — *mol-refinery-patrol:
assigned head-of-line family — deleted-`$BRANCH` park mirror + repeated
stranded-`temp` checkout-STOP (issue 374 follow-up)*. Open, P2, assigned
to `human`. One family, not two tickets.

Constraints the family inherits from this change:

- Do not route these errors into the conflict-rejection path (no
  `rejection_reason`, no delete-source/reopen-source, no polecat reroute).
- Do not weaken the missing-`$TARGET` halt.
- Do not touch merge-push (already-merged gate, ff-only tail,
  force-with-lease).
- Do not widen the issue-374 guard STOP semantics as a side effect.

W3's sealed `items/gp-sc2pz/pr-body.md`
(`sha256:fdfb77ab3621628372fb24fb91aa269080fdd80526023f2a58d8e3f80e60e32f`)
is unchanged; this copy is the W4-linked body.
````

## Appendix — `items/gp-sc2pz/evidence/stop-respawn-source.md`

sha256: b594afceff2e805ee219524ab1945bfbb61c1ee267ee7be15e2b95b65c03588b

````markdown
# Verified STOP respawn source (residual precision (a))

Measured 2026-09-22 against live `maintainer-city`.

**Finding: the respawn source is `[session_sleep]` `noninteractive = "5m"`
applied by the session reconciler.** A guard STOP does not pour a wisp,
does not fire an order, and does not mutate the work bead. Re-selection
is `find-work` after the session restarts.

See `../pr-body.md` section "Verified STOP respawn source" for the
enumerated checks (wisp sites, `gc order list`, `orphan-sweep`
`is_known_agent`, `nudge-on-route` on `bead.updated`).
````
