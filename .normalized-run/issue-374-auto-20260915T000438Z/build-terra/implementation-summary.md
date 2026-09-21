---
schema: gc.build.implementation-summary.v1
workflow:
  id: gcg--9223372036854775167
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
    - path: beads/gp-3zlmh
      hash: bead:gp-3zlmh
      role: source-anchor
      ids:
        - AC-374-04
        - AC-374-01
        - AC-374-02
        - AC-374-03
        - AC-374-05
        - AC-374-06
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
      role: deliverable-w1-suite
    - path: gastown/formulas/mol-refinery-patrol.toml
      hash: git:d46577432639c65ad3465244ce9000e50505132b
      role: dependency-w2-guarded-tree
  coverage:
    - id: AC-374-04
      status: covered
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
---

# Implementation summary — issue-374 W1 (drain item 3, lane terra)

## Summary

Executed drain item 3 (member `gp-3zlmh`, item root
`gcg--9223372036854775167`) of the terra implementation lane for run
`issue-374-auto-20260915T000438Z`: **W1 — the regression test
`test_mol_refinery_patrol_rebase_guard.sh` (D4, test-first).**

Context: the drain dispatched its items in reverse order relative to the
approved decomposition (W4 → W3 → W2 → W1 — a wiring defect escalated by
the earlier items' sessions by mail; no resolution arrived). Drain item 1
(W3, closed `pass`, root `gcg--9223372036854775181`) therefore executed
the dependency-correct sequence inside the shared session — W1's
test-first commit `ced404d`, then W2's atomic commit `d465774` — and
drain item 2 (W2, `gp-g9s7a`, closed `pass`) verified the formula+gate
half against its spec. W1's deliverable was thus already committed when
this item was claimed, with item 2's summary directing this item's
worker to *"verify against their specs and close rather than
re-implement."*

This item did exactly that: it re-read the W1 spec
(`work/decompose.md` W1 / bead `gp-3zlmh`) and design section D4, then
re-derived and re-observed **both required verification halves** —
static and behavioral — inside the authoritative worktree
(`/data/projects/gascity-packs/worktrees/normalized-06e7ae9267b1e212b5d55ab940d5b69a3df782f3810702fdfe5a7296a37540f9-terra`,
`pwd -P` verified before every command), confirming the shipped suite
satisfies every property the W1 spec names. No new commits were needed;
this item's work is the verification sweep below, this summary, and the
closure of `gp-3zlmh`.

## Intended Behavior

Per `work/decompose.md` W1, the deliverable
`gastown/tests/test_mol_refinery_patrol_rebase_guard.sh` must implement
design section D4:

- **Lift, never transcribe:** the rebase step's fenced ```bash``` block
  is lifted whole from the shipped
  `gastown/formulas/mol-refinery-patrol.toml`, sentinel-indexed on
  `git checkout -b temp origin/$BRANCH` — a sentinel that exists on
  both the unguarded and guarded trees, so reds against the base are
  behavioral, not lift errors — and executed as one unit under plain
  `bash` with `set +eu`, exercising fetch → probe → checkout ordering
  as behavior.
- **Nine legs, exactly the set the design enumerates:** 1 (skip
  preserves topology, EX-1/EX-2), 1b (stranded `temp` fails closed at
  the skip-arm checkout), 2 (diverged clean), 3 (diverged conflicting),
  4 (fetch failure stops before the probe — the stale-ref trap, with
  restore-and-rerun), 5 (missing source branch), 6 (probe error fails
  closed via a merge-base-only passthrough git shim scoped to the fence
  subshell), 7 (static structure/ordering backstop over the lifted
  text), 8 (missing-target halt composition).
- **Red-control capability built in:** `REBASE_GUARD_FORMULA` env
  override aims the identical, byte-unmodified test file at another
  tree's formula — the mechanism W3's red control depends on.
- **Hermetic fixtures:** bare origin + consumer clone per leg, isolated
  `HOME`/`GIT_CONFIG_GLOBAL`/`GIT_CONFIG_NOSYSTEM`, a PATH-shim `gc`
  stub logging every invocation as the bead-mutation oracle, and a
  declared hard `jq` dependency for the halt's wisp-pour.

All verified present and green on the shipped file — see Verification.

## Changed Files

W1's deliverable is commit
`ced404d1bc7f42f452f520c91792cfe5aa6188cd` — exactly one new file,
`git show --stat --format= ced404d` lists only:

- `gastown/tests/test_mol_refinery_patrol_rebase_guard.sh` — NEW
  (+622 lines), executable, committed test-first: `ced404d` is the
  parent of W2's `d465774` (verified via `git log` on the candidate
  branch), so the regression capability landed before the fix, exactly
  as the design's safe-split rule requires.

Total candidate-branch delta versus base `05031f2c` remains three files
(+698/−4): this suite, the D1+D2 formula change, and the D3 gate repin
— the latter two are W2's atomic deliverable, untouched by this item.
This item added no commits and modified no code; its output is this
summary and the bead closure.

## Verification

First verification command (behavioral half — the full nine-leg suite
against the guarded tree, run in the authoritative worktree after
`pwd -P` verification; observed pass, exit 0):

```console
$ cd /data/projects/gascity-packs/worktrees/normalized-06e7ae9267b1e212b5d55ab940d5b69a3df782f3810702fdfe5a7296a37540f9-terra
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

Static half (spec-required; sites enumerated on the shipped file, never
counted as a claim — observed pass):

```console
$ bash -n gastown/tests/test_mol_refinery_patrol_rebase_guard.sh   # OK, no output
```

- Red-control env override: `FORMULA="${REBASE_GUARD_FORMULA:-$ROOT/gastown/formulas/mol-refinery-patrol.toml}"`
  at `:25` (rationale comment `:21`) — the identical file can be aimed
  at another tree; the sentinel lift itself at `:89`.
- Leg 7's three count assertions, each with its distinct duty:
  probe line exactly once `:506`; lift sentinel exactly twice `:508`;
  `cannot evaluate rebase ancestry` exactly twice `:510`.
- Per-arm STOP literals contained in the lifted fence: `tracking refs
  failed` `:519`; `errored (status ` `:521`; `cannot materialize temp
  at origin/` `:523` — and asserted behaviorally in leg 1b (`:334`),
  legs 4/5 (`:415`, `:449`), leg 6 (`:485`), and as negatives in the
  halt leg 8 (`:589`–`:591`).
- Ordering chain: probe-before-capture-before-case and
  `git rebase origin/$TARGET` only after the probe, derived at `:530`.
- Test-first ordering on the candidate branch: `ced404d` (W1 suite) is
  the parent commit of `d465774` (W2 guard) — the regression test
  preceded the fix it guards.

Final proof command (artifact gate, run from the launcher rig root
after recording `gc.implementation.summary_path` on this item's root
bead; observed result: pass):

```console
$ cd /data/projects/gascity-packs
$ GC_WORK_DIR=/data/projects/gascity-packs/worktrees/normalized-06e7ae9267b1e212b5d55ab940d5b69a3df782f3810702fdfe5a7296a37540f9-terra \
  GC_BEAD_ID=gcg--9223372036854775167 .gc/scripts/checks/build-artifact-valid.sh
build artifact valid: schema=gc.build.implementation-summary.v1 path=/data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/terra/implementation-summary.md
```

## Remaining Risks

- **The red-control run itself is W3's deliverable, not W1's** (per the
  decomposition's AC split: AC-374-04 is covered by W1 *and* W3). This
  item verified the capability (`REBASE_GUARD_FORMULA` override,
  both-trees sentinel) and the guarded-tree green; the
  base-tree behavioral-red transcript (legs 1/1b/4/5/6 fail, leg 7
  static-red, legs 2/3/8 green) is recorded in
  `work/builders/terra/pr-body.md` by W3's session for the
  finalize/publish stages to carry.
- **Drain order inversion (escalated, unresolved).** The
  dispatcher/lane wiring fix is not this item's to make; this item
  completed the last of the four work items, so the lane's member set
  is now fully closed regardless.
- **CI git version.** The suite's only exact-exit assertion is leg 3's
  rebase-conflict rc 1 (measured on the host's git 2.43.0); CI's
  gastown loop should re-confirm on its git. Every other assertion is
  non-zero or wording-based by design.
- **`push=false` / `open_pr=false` for this run** — no PR exists; the
  PR-body records live at `work/builders/terra/pr-body.md`.
- **Residual-precision-(b) family is tracked, not fixed** — bead
  `gp-2rn1y` (deleted-`$BRANCH` park mirror; repeated stranded-`temp`
  checkout-STOP) remains open by design (W4's deliverable).
- **Uncovered edge recorded in the design:** `BRANCH == TARGET`
  degeneracy is asserted by design analysis only, exercised by no test
  leg — accepted by the approved design.

| ID | Status |
| --- | --- |
| AC-374-04 | covered |
| AC-374-01 | covered |
| AC-374-02 | covered |
| AC-374-03 | covered |
| AC-374-05 | covered |
| AC-374-06 | covered |
