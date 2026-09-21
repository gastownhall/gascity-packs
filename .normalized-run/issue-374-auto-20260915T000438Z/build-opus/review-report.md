---
schema: gc.build.review.v1
workflow:
  id: gcg--9223372036854774601
  formula: workflows-build-from-convoy
methodology:
  pack: gascity
  name: build-basic
producer:
  formula: workflows-build-from-convoy
  stage: review
  attempt: 1
status: approved
trace:
  upstream:
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work-contract.json
      hash: sha256:04d51caeeb64a121224cab4ed2a331b11b17f864ae437041a684306e27ba9616
      role: requirements
      ids:
        - AC-374-01
        - AC-374-02
        - AC-374-03
        - AC-374-04
        - AC-374-05
        - AC-374-06
        - AC-374-07
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/approved-design.md
      hash: sha256:057ad99d6da1db77b8fb68d5e7297b8d988eb7fffa697aea37d1638a32ce9738
      role: approved-plan
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/design-review/result.json
      hash: sha256:ba94b09ae6633749392401289d4783d9395ee060eeb97dbd987f956930b10165
      role: plan-review
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/decompose-graph.json
      hash: sha256:d1eeeeff6057de5e438a2ffced9a51f40047ff6c64946fa10a143a852415a4a3
      role: decomposition
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/implementation-summary.md
      hash: sha256:df5134440fd4add31e50fa28456645f3649a710258564803acb265a1352be0c4
      role: implementation-summary
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/drain-items/3-gp-zyrv0/pr-body.md
      hash: sha256:981eb12a3c6eb4bf952724e80aa386d5c291d0a4cb65f78cea35faa64d16fe27
      role: verification-records
    - path: /data/projects/gascity-packs/worktrees/normalized-3f91225712f8005e7b62ea43969101c0aa92df53258931f464bdd57cc963f24a-opus
      hash: git:9b8951553f9e4c57effb84865cf2a1f282a467a1
      role: review-subject
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

# Review — issue-374 opus implementation (`build-from-review-base` review stage)

Review subject: branch
`normalized/3f91225712f8005e7b62ea43969101c0aa92df53258931f464bdd57cc963f24a/opus`,
base `05031f2c66e080865c379ff799c7369430560a8f`, head
`9b8951553f9e4c57effb84865cf2a1f282a467a1` (worktree clean, head matches the
workflow root's recorded `gc.build.review_subject_head_sha`, base is an
ancestor of head). Two commits, test-first: `8d087e0` (nine-leg regression
suite, +687) then `9b89515` (formula guard + gate repin, +60/−5 and +33). Diff
confined to exactly the three files the approved design names.
`review_mode=report`: no code was mutated by this review; every result below
was independently reproduced in detached scratch worktrees
(`git worktree add --detach`), never in the shared implementation worktree.
The drain aggregate's item mapping (dirs `2-gp-hptxz`/`3-gp-zyrv0` keyed by
source anchor, members `gp-rxjes`/`gp-rccpu`) was used to line items up with
the decomposition's four W1–W4 nodes.

## Verdict

**approved.**

The implementation is a faithful, high-quality execution of the approved
design. The D1 fence is byte-contained in the shipped formula, D2's three
prose amendments are present verbatim, D3's five new pins are placed exactly
as specified (site-unique where designed, deliberately two-site for the
collective sentence) with the anti-fix rationale carried into gate comments,
and the D4 suite passes all nine legs on the guarded tree while the red
control reproduces the design's exact per-leg pattern against the unguarded
base. All seven contract ACs are implemented and verified. The defect that
blocked the sibling terra lane — the new test file tripping the CI-required
bare-`bd` linter — does **not** recur here: the opus suite routes every beads
literal through `gc `, `tests/test_no_bare_bd_commands.py` passes on both
trees, and the full `ci.yml:44` pytest sweep is green on the fix tree apart
from one pre-existing, base-identical, environment-local failure. A mutation
control independently confirmed the suite's kill-coverage on the historically
witness-free arm (the exit-checked skip-arm checkout). Remaining risks are
documented, bounded, and design-sanctioned; none is a defect of this change.

## Findings

No Blocker, Major, or Minor defects. One nit, plus observations.

### N1 [Nit] Dead per-leg bookkeeping variable

`test_mol_refinery_patrol_rebase_guard.sh:83,:103` — `LEG_ORDER` is
initialized and appended per leg but never read; the summary and exit logic
use only `LEG_RESULT`. Two dead lines; harmless. Fold into any future edit of
the file rather than churning the branch for it.

### Observations (not defects of this change)

- **Leg 3's exact `rc 1` assertion is the one CI-sensitive carve-out**
  (`:482`). Git documents only "non-zero on conflict"; 1 is the empirically
  stable code measured here on git 2.43.0, and CI runs 2.52. The design
  explicitly sanctions this scoped carve-out and requires re-confirmation on
  the CI git; the builders flagged it in-file and in W1/W2/W3 summaries.
  Since `push=false`/`open_pr=false` for this run, first CI contact happens
  at PR time — this is the single most likely source of a first-run CI red,
  and it would indict the assertion's spelling, not the guard.
- **`tests/test_gastown_lint_findings.py::test_every_universal_waiver_entry_is_still_reported`
  fails locally on BOTH the base and fix scratch trees** (five `named_session`
  waiver entries no longer reported by the local dev `gc`) — pre-existing
  environmental divergence, not introduced or worsened by this change. In
  CI's `:44` sweep the test self-skips (no `gc` on PATH until a later step
  installs one) and is gated separately at `:84` against the installed
  `gc@latest`.
- **The builders' "full suite" (design step 6) is the gastown shell loop,
  not CI's pytest sweep.** W3 declared this bound explicitly in Remaining
  Risks rather than papering over it. This review closed the gap: the exact
  `ci.yml:44` command on the fix tree returns 1595 passed / 39 skipped /
  9586 subtests with only the pre-existing failure above. The differential
  that blocked terra is clean here.
- **W4 adopted the sibling terra lane's tracker bead `gp-2rn1y` instead of
  filing a duplicate.** Verified live: open, P2, routed to `human`, title
  matching the PR-body link, additive `normalized.adopted_by_run/anchor/lane`
  stamps present, terra's `normalized.run_id` and description intact. Beads
  are shared-store state while branches are lane-local; a second identical
  P2 would degrade the tracking the design requires. The deviation is
  declared in W4's summary and matches rig precedent for cross-lane tracker
  items. Design verification step 9 is satisfied.
- **The STOP respawn source (residual precision (a)) is a
  configuration-and-code trace, not a live refinery observation** — the
  live city instantiates no refinery agent, so no STOP→respawn cycle could
  be watched. The finding (city `[session_sleep]` restart policy; three
  plausible recovery paths proven inert, including `orphan-sweep`'s
  `is_known_agent` short-circuit) is recorded with its limitation in
  `2-gp-hptxz/evidence/stop-respawn-source.md`. The design asked for a
  production-rig measurement; this is the closest the environment allows,
  stated rather than assumed.
- **The harness deliberately departs from the witness suites' fail-fast
  style**: errexit stays live for harness/fixture preconditions, but leg
  assertions route through `bad` so the run continues and reports per-leg —
  which the design's red control requires ("enumerated, never a count").
  Declared in-file (`:27-:30`) and in W1's summary; unlike the terra
  implementation, the in-file comments accurately describe the mechanism in
  force.

## Verification

All commands run 2026-09-21 in detached scratch worktrees `/tmp/rv374opus-fix`
(head `9b89515`) and `/tmp/rv374opus-base` (`05031f2c`), git 2.43.0, Python
3.12, jq 1.7; removed after review.

1. **Input binding, no drift:** recomputed sha256 of the work contract
   (`04d51cae…`), approved design (`057ad99d…` — also the digest
   `design-review/result.json` declares for the final candidate), plan
   review (`ba94b09a…`, status=approved / verdict=done /
   global_verdict=approve, all 7 AC ids), decomposition graph (`d1eeeeff…`),
   drain-aggregate summary (`df513444…` — matches the root's
   `gc.build.implementation_summary_sha256`), all four per-item summaries
   (`90ca77fc…`, `52c59457…`, `85751a6b…`, `d09afc9f…` — match the
   aggregate's trace), both PR bodies (`22e5a64f…` W3 seal intact,
   `981eb12a…` W4 record). Subject worktree clean at the recorded head;
   `gc.attempt=1`; no prior fix attempts recorded on the root.
2. **Design fidelity:** the design's 44-line D1 fence is byte-contained in
   the shipped `gastown/formulas/mol-refinery-patrol.toml`; D2.1 (SKIP
   success paragraph), D2.2 ("and only then" conflict preamble), D2.3
   (intro rationale sentence) all present; base `:248-:293` (prune fetch +
   missing-target halt) re-hashes byte-identical on the fix tree at
   `:252-:297` (`c7d4683f…` both sides — the hash W2's summary claims);
   `git diff --numstat base..head` = exactly the formula (+60/−5), the new
   test (+687), the gate (+33). Merge-push, find-work, and the conflict
   tail are untouched.
3. **Guarded tree:** `bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh`
   → all nine legs PASS, rc 0.
4. **Red control (AC-374-04):** identical fix-tree test file,
   `REBASE_GUARD_FORMULA=/tmp/rv374opus-base/gastown/formulas/mol-refinery-patrol.toml`
   → legs 1, 1b, 4, 5, 6 FAIL behaviorally, leg 7 FAILS statically, legs 2,
   3, 8 PASS — exactly the design's enumerated expectation, and exactly what
   W1/W3 recorded.
5. **Mutation control (suite teeth):** deleting only the skip-arm checkout
   exit-check from a copy of the fix formula reds exactly legs 1b
   (behavioral) and 7 (static) while all other legs stay green — the
   iter-2 design review's kill-coverage mandate for this arm holds in the
   shipped suite, independently reproduced.
6. **Inference gate (AC-374-07):**
   `python3 -m pytest tests/test_gascity_pack_inference_gate.py -q` → 89
   passed. Pin sites enumerated on the fix tree (sites, not counts): guard
   fetch `:304` only (merge-push's braced twin `:845` is a distinct
   string); probe `:315` only; `ANCESTOR_RC=$?` `:316` only (merge-push
   `:851` uses `ANCESTOR_STATUS`); collective STOP sentence `:305` + `:337`
   exactly (the designed two-site pin); `echo "SKIP-REBASE:` `:327` only;
   preserved `git rebase origin/$TARGET` `:332` (the `1)` arm); checkout
   sentinel `:322` (exit-checked skip arm) + `:331` (bare diverged arm);
   `errored (status ` at `:337` + merge-push `:881` — confirming the
   absorption rationale for keeping it a leg-7 literal rather than a gate
   pin. Gate file's `mol-refinery-patrol` sites: `:91` (prose dict),
   `:122` (command dict, repinned, insertion-only), `:823` (registry,
   unchanged, moved from base `:790` under the insertion).
7. **CI parity vs `.github/workflows/ci.yml`:** pytest sweep (`:44`, exact
   command) on the fix tree → 1 failed, 1595 passed, 39 skipped, 9586
   subtests — the one failure is the pre-existing lint-findings waiver test
   (fails identically at base; self-skips in CI's `:44` context).
   Differential linter check: `tests/test_no_bare_bd_commands.py` → 2
   passed on the fix tree AND at base — the terra lane's blocking defect
   does not exist in this implementation (every beads literal in the new
   suite reads `gc bd …`, including the stub's case arms and the `$GC_LOG`
   oracle patterns). Gastown shell loop (`:88`): all 7
   `gastown/tests/test_*.sh` rc 0 on the fix tree. Steps `:64/:65/:75/:84`
   depend on a freshly installed `gc@latest` and are environment-bound;
   this change touches no pack manifest, role prompt, or lint waiver they
   read.
8. **AC closure:** AC-374-01 (exit-checked dual-refspec force-fetch after
   the halt, fail-closed, no bead mutation — legs 4/5 + `$GC_LOG` oracle);
   AC-374-02 (skip with topology intact: SHA equality, merge count 2,
   source ref unchanged — leg 1 on EX-1/EX-2; leg 1b for the checkout-STOP);
   AC-374-03 (probe rc≠0/1 STOPs, never read as "not an ancestor" — leg 6);
   AC-374-04 (red→green demonstrated both directions, items 3–4 above);
   AC-374-05 (diverged rc=1 arm preserves today's adjacent checkout+rebase
   pair byte-identically — legs 2/3 green on both trees); AC-374-06 (halt
   byte-identical by hash and fires first — leg 8 both trees; STOP arms
   carry no rejection metadata, no reopen/delete, no reroute; merge-push
   untouched; leg 7 pins composition order statically); AC-374-07 (formula
   and gate in the single commit `9b89515`; gate green; sites enumerated,
   item 6 above).
9. **Tracking (design step 9):** `gp-2rn1y` exists, open, P2, routed to
   `human`, adoption stamps verified live; linked from the PR body of
   record (`3-gp-zyrv0/pr-body.md:256`) with the family's constraints.

Coverage matrix (review coverage of upstream ACs):

| ID | Status |
| --- | --- |
| AC-374-01 | covered |
| AC-374-02 | covered |
| AC-374-03 | covered |
| AC-374-04 | covered |
| AC-374-05 | covered |
| AC-374-06 | covered |
| AC-374-07 | covered |
