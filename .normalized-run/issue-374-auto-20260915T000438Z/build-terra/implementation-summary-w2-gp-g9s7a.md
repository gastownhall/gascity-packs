---
schema: gc.build.implementation-summary.v1
workflow:
  id: gcg--9223372036854775172
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
    - path: beads/gp-g9s7a
      hash: bead:gp-g9s7a
      role: source-anchor
      ids:
        - AC-374-01
        - AC-374-02
        - AC-374-03
        - AC-374-05
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
    - path: gastown/formulas/mol-refinery-patrol.toml
      hash: git:d46577432639c65ad3465244ce9000e50505132b
      role: deliverable-d1d2-formula
    - path: scripts/gascity_pack_inference_gate.py
      hash: git:d46577432639c65ad3465244ce9000e50505132b
      role: deliverable-d3-gate-repin
    - path: gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
      hash: git:ced404d1bc7f42f452f520c91792cfe5aa6188cd
      role: dependency-w1-suite
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

# Implementation summary — issue-374 W2 (drain item 2, lane terra)

## Summary

Executed drain item 2 (member `gp-g9s7a`, item root
`gcg--9223372036854775172`) of the terra implementation lane for run
`issue-374-auto-20260915T000438Z`: **W2 — D1+D2 formula guard insertion
and D3 inference-gate repin, atomic.**

Context: the drain dispatched its items in reverse order relative to the
approved decomposition (W4 → W3 → W2 → W1 — a wiring defect escalated by
drain item 0 and item 1's session by mail, no resolution having arrived).
Item 1 (W3, closed `pass`, root `gcg--9223372036854775181`) therefore
executed the dependency-correct sequence inside the shared session — W1's
test-first commit `ced404d`, then W2's atomic commit `d465774` — and left
`gp-g9s7a` open for this item with the deliverables already committed and
its summary recording: *"their workers should verify against their specs
and close rather than re-implement."*

This item did exactly that: it re-read the W2 spec
(`work/decompose.md` W2 / bead `gp-g9s7a`) and the approved design's
D1/D2/D3 obligations, re-derived every pinned-literal site and line
grounding on the fixed tree rather than trusting the prior session's
citations, re-ran both required verification halves (static and
behavioral) inside the authoritative worktree
(`/data/projects/gascity-packs/worktrees/normalized-06e7ae9267b1e212b5d55ab940d5b69a3df782f3810702fdfe5a7296a37540f9-terra`,
`pwd -P` verified before every command), and confirmed the atomicity
requirement (one commit `d465774` carries D1+D2+D3 together — never
formula without gate). No new commits were needed; the deliverable was
already complete and correct. This item's work is the verification sweep
below plus this summary and the closure of `gp-g9s7a`.

## Intended Behavior

Per `work/decompose.md` W2 and the approved design, commit `d465774`
must deliver, in one atomic commit:

- **D1 (pure insertion):** between the missing-target halt's closing `fi`
  and the rebase, in the order prune-fetch → halt → guard-fetch → probe →
  case: an explicit dual-refspec force fetch of exactly the two tracking
  refs the decision reads (`+refs/heads/$BRANCH` and `+refs/heads/$TARGET`
  → `refs/remotes/origin/…`), exit-checked — on failure, echo + drain-ack
  + exit 1 before any probe (a stale-ref skip decision is the trap);
  then `git merge-base --is-ancestor "origin/$TARGET" "origin/$BRANCH"`
  probed before any branch exists, captured into `ANCESTOR_RC` (not
  `status`; zsh read-only collision); then a three-way case — rc 0
  materializes `temp` at `origin/$BRANCH` (the checkout itself
  exit-checked over a stranded stale `temp`) and narrates `SKIP-REBASE`
  down the normal success path; rc 1 runs byte-identically the two lines
  the step has always run (`git checkout -b temp origin/$BRANCH` +
  `git rebase origin/$TARGET`); any other rc STOPs without rebasing.
  Every STOP arm is echo + drain-ack + exit only — no rejection_reason,
  no reopen/delete-source, no polecat reroute, no bead mutation.
- **D2 (three prose amendments, nothing removed):** the intro sentence
  before the fence (the block also decides whether a rebase is needed at
  all), the skip-success paragraph after the fence (treat SKIP-REBASE as
  a succeeded rebase; proceed to run-tests; do not abort/amend/reset),
  and the conflict-preamble amendment (what reaches a failed rebase is a
  genuine content conflict).
- **D3 (gate repin in lockstep):** `GASTOWN_BUILD_WORKFLOW_CONTRACTS`
  `mol-refinery-patrol` keeps the preserved pin `git rebase origin/$TARGET`
  and adds five fragments witnessing the new step text (guard fetch,
  direction-locked probe, `ANCESTOR_RC=$?`, the shared fail-closed
  sentence, the `echo "SKIP-REBASE:` anchor).

Verified present on the fixed tree exactly as specified — see
Verification for the site enumeration.

## Changed Files

Versus base `05031f2c66e080865c379ff799c7369430560a8f`, `git diff
05031f2..HEAD --stat` lists exactly three files:

- `gastown/tests/test_mol_refinery_patrol_rebase_guard.sh` — NEW (+622),
  commit `ced404d1bc7f42f452f520c91792cfe5aa6188cd` (W1's deliverable,
  test-first; dependency of this item, verified green by this sweep).
- `gastown/formulas/mol-refinery-patrol.toml` — +59/−4, commit
  `d46577432639c65ad3465244ce9000e50505132b` (D1 insertion + D2.1/D2.2/D2.3
  prose; the only deleted lines are the two original checkout/rebase lines
  absorbed verbatim into the `1)` arm and the two D2.2-amended preamble
  lines).
- `scripts/gascity_pack_inference_gate.py` — +17/−0, same commit
  `d465774` (D3: five added fragments after the preserved pin) — the
  atomicity requirement is satisfied by construction: one commit carries
  formula and gate together.

This item added no commits and modified no product code; its output is
this summary and the bead closure.

## Verification

First verification command (behavioral half — W1's nine-leg suite against
the guarded tree, run in the authoritative worktree after `pwd -P`
verification; observed pass, exit 0):

```console
$ cd /data/projects/gascity-packs/worktrees/normalized-06e7ae9267b1e212b5d55ab940d5b69a3df782f3810702fdfe5a7296a37540f9-terra
$ bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
leg leg1: PASS   (skip, conflicting merge-heavy shape — topology preserved)
leg leg1b: PASS  (skip, clean merge-heavy shape — no flattening)
leg leg2: PASS   (diverged clean — existing rebase path, rc 0)
leg leg3: PASS   (diverged conflicting — existing conflict path, rc 1)
leg leg4: PASS   (fetch failure — STOP before any decision, stale-ref trap closed)
leg leg5: PASS   (missing source branch — fails at the guarded fetch, rc ≠ 0)
leg leg6: PASS   (probe error — STOP, never read as "not an ancestor")
leg leg7: PASS   (static structure/ordering backstop over the lifted fence)
leg leg8: PASS   (missing-target halt composition)
rebase-guard suite: all legs pass
```

Static half — inference gate green on the changed tree (observed pass):

```console
$ python3 -m pytest tests/test_gascity_pack_inference_gate.py -q
89 passed in 2.89s
```

Pinned-literal site enumeration (re-derived on the fixed tree; sites
enumerated, never counted). In `gastown/formulas/mol-refinery-patrol.toml`:
guard fetch `:304`; direction-locked probe `:315`; `ANCESTOR_RC=$?` `:316`;
the shared fail-closed sentence `:305` (fetch arm) and `:337` (probe-error
arm); `echo "SKIP-REBASE:` `:327`; preserved unquoted pin
`git rebase origin/$TARGET` `:332` (single site, inside the `1)` arm).
In `scripts/gascity_pack_inference_gate.py`: preserved pin `:124`; guard
fetch `:129`; probe `:131`; `ANCESTOR_RC=$?` `:134`; fail-closed sentence
`:138`; `SKIP-REBASE` anchor `:141`.

Diff confinement (design step 2, re-verified): the formula diff has
exactly two hunks (`@@ -244,6 +244,10 @@` D2.3 intro; `@@ -291,14 +295,65 @@`
D1 insertion + D2.1 + D2.2). Base `:248` (`git fetch --prune origin`) and
the halt body `:249-:293` appear only as context lines; the conflict tail
beyond the amended preamble and merge-push (already-merged gate, ff-only
tail, force-with-lease push) have no hunks. CI-parity gastown loop
(observed pass, 7/7):

```console
$ for t in gastown/tests/test_*.sh; do bash "$t"; done
PASS test_gastown_pack_assets.sh        PASS test_gastown_theme_scripts.sh
PASS test_mol_refinery_patrol_rebase_guard.sh
PASS test_mol_witness_patrol_orphan_recovery.sh
PASS test_polecat_churn_watcher.sh      PASS test_polecat_push_gate.sh
PASS test_witness_heartbeat_check.sh
```

Final proof command (artifact gate, run from the launcher rig root after
recording `gc.implementation.summary_path` on this item's root bead;
observed result: pass):

```console
$ cd /data/projects/gascity-packs
$ GC_BEAD_ID=gcg--9223372036854775172 .gc/scripts/checks/build-artifact-valid.sh
build artifact valid: schema=gc.build.implementation-summary.v1 path=/data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/terra/implementation-summary-w2-gp-g9s7a.md
```

## Remaining Risks

- **Drain order remains inverted (escalated, unresolved).** The
  dispatcher/lane wiring fix is not this item's to make. Downstream drain
  item 3 (W1, `gp-3zlmh`) will find its deliverable already committed
  (`ced404d`, verified green by this sweep); its worker should verify
  against its spec and close rather than re-implement.
- **CI git version.** The suite's only exact-exit assertion is leg 3's
  rebase-conflict rc 1 (measured on the host's git 2.43.0). CI's gastown
  loop should re-confirm on its git; every other assertion is non-zero or
  wording-based by design.
- **`push=false` / `open_pr=false` for this run** — no PR exists yet; the
  PR-body records (including the red-control transcript, which is W3/AC-374-04
  evidence, not this item's) live at `work/builders/terra/pr-body.md` for
  the finalize/publish stages to carry.
- **Residual-precision-(b) family is tracked, not fixed** — bead
  `gp-2rn1y` (deleted-`$BRANCH` park mirror; repeated stranded-`temp`
  checkout-STOP) remains open by design; the stranded-`temp` case is
  fail-closed by the skip-arm checkout check but not auto-recovered.
- **Uncovered edge recorded in the design:** `BRANCH == TARGET` degeneracy
  is asserted by design analysis only, exercised by no test leg — accepted
  by the approved design.

| ID | Status |
| --- | --- |
| AC-374-01 | covered |
| AC-374-02 | covered |
| AC-374-03 | covered |
| AC-374-05 | covered |
| AC-374-06 | covered |
| AC-374-07 | covered |
