---
schema: gc.build.implementation-summary.v1
workflow:
  id: gcg--9223372036854775181
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
    - path: beads/gp-yk0ku
      hash: bead:gp-yk0ku
      role: source-anchor
      ids:
        - AC-374-04
        - AC-374-06
        - AC-374-07
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work-contract.json
      hash: sha256:04d51caeeb64a121224cab4ed2a331b11b17f864ae437041a684306e27ba9616
      role: work-contract
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/approved-design.md
      hash: sha256:057ad99d6da1db77b8fb68d5e7297b8d988eb7fffa697aea37d1638a32ce9738
      role: approved-plan
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/decompose.md
      hash: sha256:84a9b1833164f4de4c61b8b700d73270a66fb1b5ec146e27ebc3fc58d1a26b5c
      role: decomposition
    - path: gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
      hash: git:ced404d1bc7f42f452f520c91792cfe5aa6188cd
      role: deliverable-w1-test
    - path: gastown/formulas/mol-refinery-patrol.toml
      hash: git:d46577432639c65ad3465244ce9000e50505132b
      role: deliverable-w2-formula-and-gate
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/terra/pr-body.md
      hash: sha256:02b688b30d3941c8e3b913782eb2098b457130d5fa629967c5a7c0cf6acb4bc4
      role: pr-body-records
    - path: beads/gp-2rn1y
      hash: bead:gp-2rn1y
      role: filed-follow-up-tracking
  coverage:
    - id: AC-374-01
      status: covered
    - id: AC-374-02
      status: covered
    - id: AC-374-03
      status: covered
    - id: AC-374-04
      status: covered
    - id: AC-374-05
      status: covered
    - id: AC-374-06
      status: covered
    - id: AC-374-07
      status: covered
---

# Implementation summary — issue-374 W3 (drain item 1, lane terra)

## Summary

Executed drain item 1 (member `gp-yk0ku`, item root
`gcg--9223372036854775181`) of the terra implementation lane for run
`issue-374-auto-20260915T000438Z`: **W3 — red control, full verification
sweep, and PR-body records.**

W3's deliverables require W1's regression test and W2's guarded formula to
exist. The drain dispatched its items in reverse order relative to the
approved decomposition (W4 → W3 → W2 → W1 — a wiring defect escalated by
drain item 0 as mail `gcg--9223372036854775182` and by this session as mail
`gcg--9223372036854775176`, no resolution having arrived), and
`gc.drain_on_item_failure=skip_remaining` would have discarded the entire
implementation had this item simply failed. Because the design's split rule
is explicit — *"the only safe split is test-first (D4 plus its red control
against the unguarded base), then formula+gate atomically — never formula
without gate (AC-374-07)"* — this item executed the dependency-correct
sequence inside the shared session and then performed W3's own work:

1. W1's deliverable as commit `ced404d` (test-first): the regression suite
   `gastown/tests/test_mol_refinery_patrol_rebase_guard.sh` (design D4,
   nine legs, lift-not-transcribe, `REBASE_GUARD_FORMULA` override).
2. W2's deliverable as commit `d465774` (one atomic commit): the D1 guarded
   ancestry decision inserted between the missing-target halt and the
   rebase, the D2 step-prose amendments, and the D3 inference-gate repin
   (one preserved pin plus five new fragments).
3. W3's own deliverables: the red control against the unguarded base via
   the design's detached-worktree mechanism, the full verification sweep
   (design steps 2–8), and the PR-body records at
   `work/builders/terra/pr-body.md`, including the production-rig-measured
   STOP respawn source and the pinned-literal site enumeration.

The worktree
(`/data/projects/gascity-packs/worktrees/normalized-06e7ae9267b1e212b5d55ab940d5b69a3df782f3810702fdfe5a7296a37540f9-terra`)
was verified (`pwd -P`) before every source read, edit, test, and commit.
Work beads `gp-g9s7a` (W2) and `gp-3zlmh` (W1) were left open for their
drain items, whose workers will find their deliverables already committed
and verified; the commits' messages name the work items.

## Intended Behavior

Per `work/decompose.md` W3 (`gp-hptxz`, materialized as `gp-yk0ku`):
design verification steps 3–8 — run the identical test file against the
unguarded base via `git worktree add --detach <tmp> 05031f2c` plus
`REBASE_GUARD_FORMULA`, expecting (enumerated per leg, never counted) legs
1, 1b, 4, 5, 6 to fail behaviorally, leg 7 to fail statically, and legs 2,
3, 8 to stay green; then all nine green on the fixed tree; record the
mechanism and git versions, the no-errexit assumption, the deliberate
`1)`-arm bare-checkout asymmetry, the no-successor-wisp confirmation, and
the **verified** STOP respawn source measured against a production rig;
enumerate every pinned-literal site in the PR-body records; link the W4
follow-up bead (`gp-2rn1y`).

The guard's intended behavior (delivered by `d465774`, verified by the
suite): explicit dual-refspec force fetch of both tracking refs with its
exit checked (STOP before any decision, no bead mutation);
`git merge-base --is-ancestor "origin/$TARGET" "origin/$BRANCH"` probed
before any branch exists and captured into `ANCESTOR_RC`; rc 0 skips the
rebase with `temp` materialized SHA-identical to `origin/$BRANCH` (the
skip-arm checkout itself exit-checked over a stranded stale `temp`); rc 1
runs the preserved unquoted `git rebase origin/$TARGET` exactly as today;
any other rc STOPs without rebasing and without mutating bead state. The
prune fetch, the missing-target halt, the conflict tail, and merge-push
are untouched.

## Changed Files

- `gastown/tests/test_mol_refinery_patrol_rebase_guard.sh` — NEW (+622
  lines), commit `ced404d` (W1 deliverable, test-first). Nine-leg witness
  suite; hermetic bare-origin fixtures (EX-1/EX-2/EX-3a/EX-3b); PATH-shim
  `gc` stub as the bead-mutation oracle; real `jq` for the halt's
  wisp-pour; merge-base-only `git` shim scoped to the fence subshell;
  static structure/ordering backstop over the lifted fence text.
- `gastown/formulas/mol-refinery-patrol.toml` — +63/−4 across two hunks
  (D1 insertion between the halt's `fi` and the rebase; D2.3 intro
  sentence; D2.1 skip-success paragraph; D2.2 conflict-preamble
  amendment), commit `d465774` (W2 deliverable, atomic with the gate).
- `scripts/gascity_pack_inference_gate.py` — +17 (D3: five new fragments
  in `GASTOWN_BUILD_WORKFLOW_CONTRACTS["mol-refinery-patrol"]` after the
  preserved `git rebase origin/$TARGET` pin), same commit `d465774`.

Nothing else changes: `git diff 05031f2..HEAD --stat` lists exactly these
three files; the only deleted lines in the formula are the two fence lines
absorbed verbatim into the `1)` arm and the two D2.2-amended preamble
lines.

## Verification

First verification command (the design's red control, run against the
unguarded base via the detached-worktree mechanism — the fix-tree test
file byte-unmodified, only the formula pointer moved):

```console
$ git worktree add --detach <tmp> 05031f2c
$ REBASE_GUARD_FORMULA=<tmp>/gastown/formulas/mol-refinery-patrol.toml \
    bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
leg leg1: FAIL  (behavioral — artificial conflict: "could not apply … side B",
                 CONFLICT (content): Merge conflict in shared.txt, rc 1)
leg leg1b: FAIL (behavioral — bare checkout failed silently, unguarded rebase
                 ran against the detached HEAD, rc 0, no STOP wording)
leg leg2: PASS
leg leg3: PASS
leg leg4: FAIL  (behavioral — block proceeded on stale refs; no fetch-STOP
                 wording; temp created)
leg leg5: FAIL  (behavioral — missing branch surfaced late at checkout, rc 0)
leg leg6: FAIL  (behavioral — no probe on base, no STOP wording)
leg leg7: FAIL  (static — probe line occurs 0 times in the lifted base fence)
leg leg8: PASS
FAIL: rebase-guard suite incomplete (see legs above)      # exit 1, expected
```

Mechanism and versions recorded in the PR-body records: git 2.43.0, GNU
bash 5.2.21, jq 1.7.

Green sweep on the fixed tree (`d465774`) — observed pass:

```console
$ bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
leg leg1: PASS … leg leg8: PASS
rebase-guard suite: all legs pass                            # exit 0

$ python3 -m pytest tests/test_gascity_pack_inference_gate.py -q
89 passed in 2.99s

$ for t in gastown/tests/test_*.sh; do bash "$t"; done       # CI's loop
all 7 gastown test files pass (witness/heartbeat/polecat untouched)
```

Diff confinement (design step 2): verified — three files only; `:248`
prune fetch, halt `:249-:293`, conflict tail, and merge-push untouched;
all pinned-literal sites enumerated (never counted) in the PR-body
records, including the gate-file sites (`:91` prose dict, `:122` command
dict, `:807` registry). The no-successor-wisp property is confirmed
statically: no `bd mol wisp` site falls inside the guard block
(`:298`–`:341`). The STOP respawn source is verified against a production
rig (live controller `gc nudge poll` on `maintainer-city`;
reconciler-spawned sessions; session-sleep/idle-interval restart policy)
— full measurement in the PR-body records.

Final proof command (artifact gate, run from the launcher rig root after
recording `gc.implementation.summary_path` on the item root bead;
observed result: pass):

```console
$ cd /data/projects/gascity-packs
$ GC_BEAD_ID=gcg--9223372036854775181 .gc/scripts/checks/build-artifact-valid.sh
build artifact valid: schema=gc.build.implementation-summary.v1 path=/data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/terra/implementation-summary.md
```

## Remaining Risks

- **Drain order remains inverted (escalated, unresolved).** The
  dispatcher/lane wiring fix is not this item's to make. Downstream drain
  items 2 (W2, `gp-g9s7a`) and 3 (W1, `gp-3zlmh`) will find their
  deliverables already committed (`d465774`, `ced404d` respectively,
  verified by this item's sweep); their workers should verify against
  their specs and close rather than re-implement. Mails
  `gcg--9223372036854775182` (item 0) and `gcg--9223372036854775176`
  (this session) document the defect.
- **CI git version.** The suite's only exact-exit assertion is leg 3's
  rebase-conflict rc 1 (measured on git 2.43; the host runner). CI's
  gastown loop should re-confirm on its git; every other failure
  assertion is strictly non-zero or wording-based by design.
- **`push=false` / `open_pr=false` for this run** — no PR exists yet; the
  PR-body records live at `work/builders/terra/pr-body.md` for the
  finalize/publish stages to carry, including the link to follow-up bead
  `gp-2rn1y` (design step 9's obligation lands when the PR opens).
- **Residual-precision-(b) family is tracked, not fixed** — bead
  `gp-2rn1y` (deleted-`$BRANCH` park mirror; repeated stranded-`temp`
  checkout-STOP) remains open by design.
- **Uncovered edge recorded in the design:** `BRANCH == TARGET` degeneracy
  (probe rc 0, no-op landing) is asserted by design analysis only,
  exercised by no test leg — accepted by the approved design.

| ID | Status |
| --- | --- |
| AC-374-01 | covered |
| AC-374-02 | covered |
| AC-374-03 | covered |
| AC-374-04 | covered |
| AC-374-05 | covered |
| AC-374-06 | covered |
| AC-374-07 | covered |
