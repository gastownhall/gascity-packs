---
schema: gc.build.implementation-summary.v1
workflow:
  id: gcg--9223372036854775499
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
    - path: beads/gp-ikbyp
      hash: bead:gp-ikbyp
      ids:
        - AC-374-01
        - AC-374-02
        - AC-374-03
        - AC-374-04
        - AC-374-05
        - AC-374-06
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/approved-design.md
      hash: sha256:057ad99d6da1db77b8fb68d5e7297b8d988eb7fffa697aea37d1638a32ce9738
    - path: gastown/formulas/mol-refinery-patrol.toml
      hash: sha256:c5a2da6391b1cb2c20334322e892bb5a95873d145f319c7946347a3816e0f1d8
    - path: gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
      hash: git:8d087e08c4d346ed2dfd7e169bc6ccf691cc9d17
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
---

# issue-374 W1 — regression test for the mol-refinery-patrol rebase-skip guard

## Summary

Drain item 0 (member `gp-yzkjn`, source anchor `gp-ikbyp`) of convoy
`gp-afmpx`. Implements design section **D4**: a nine-leg witness suite at
`gastown/tests/test_mol_refinery_patrol_rebase_guard.sh` covering the ancestry
decision in `mol-refinery-patrol`'s `rebase` step, plus the permanent
red-control capability.

This is the **test-first** item, so the guard itself (D1/D2) is deliberately
**not** applied here — that is W2 (`gp-zcsrt`). The deliverable is therefore
expected to be red on the current tree, and the value of the item is that the
red is the *exact* red D4 predicts. Both halves were measured (see
`## Verification`): against the unguarded base formula legs 1, 1b, 4, 5 and 6
fail behaviorally and leg 7 fails statically, while legs 2, 3 and 8 stay green;
against a guarded formula all nine legs pass.

The suite lifts the step's fenced bash block whole from the shipped TOML rather
than transcribing it, using the sentinel `git checkout -b temp origin/$BRANCH`,
which is present in both the unguarded and the guarded formula — so a red is
behavioral, never a lift error.

## Intended Behavior

The `rebase` step used to run `git checkout -b temp origin/$BRANCH` followed by
`git rebase origin/$TARGET` unconditionally. When `origin/$TARGET` is already an
ancestor of `origin/$BRANCH` the source is a pure fast-forward candidate, and
rebasing it drops merge commits together with their recorded conflict
resolutions — producing either an artificial conflict on an unchanged SHA (the
rejection treadmill) or a silent flattening that merge-push then force-pushes
over the source branch.

The suite pins the guarded behavior D1 specifies:

| Leg | Pins |
| --- | --- |
| 1 | already-based sources skip the rebase with topology intact (EX-1 conflicting, EX-2 clean): rc 0, `SKIP-REBASE:` narration, `temp` SHA-identical to `origin/source`, merge count still 2, no rebase in progress, `origin/source` never rewritten |
| 1b | a stranded `temp` fails closed at the skip-arm checkout: non-zero rc, `cannot materialize temp at origin/` STOP, stale branch left exactly as found, no branch switch, no `temp2` |
| 2 | genuinely diverged + clean still rebases as today (no skip, `origin/main` an ancestor of the rebased `temp`) |
| 3 | genuinely diverged + conflicting keeps the existing conflict path (rc 1, rebase in progress, zero mutation) |
| 4 | a failed fetch stops before the probe — the stale-ref trap: stale tracking refs would still satisfy an ancestor probe, so the fence must STOP, create no `temp`, and decide differently once the refs are fresh |
| 5 | a missing source branch fails closed at the explicit fetch, before any probe or checkout |
| 6 | a probe error is never read as "not an ancestor": `errored (status 128)` STOP, no `temp`, rebase unreached |
| 7 | structural backstop and composition order on the raw lifted text (static) |
| 8 | the missing-target halt still fires first and is untouched by the guard |

Every non-halt leg additionally asserts **zero bead mutation** through a `gc`
PATH stub that logs each invocation: a tooling error is not a conflict, so no
STOP arm may write bead state.

## Changed Files

| File | Change |
| --- | --- |
| `gastown/tests/test_mol_refinery_patrol_rebase_guard.sh` | new (added, executable); the whole deliverable |

Commit `8d087e0` on branch
`normalized/3f91225712f8005e7b62ea43969101c0aa92df53258931f464bdd57cc963f24a/opus`,
parent `05031f2` (`normalized.base_sha`). No other file is touched; in
particular `gastown/formulas/mol-refinery-patrol.toml` is **unchanged**, as
W1 requires.

## Verification

Both halves of D4 were measured. All commands were run from the authoritative
worktree
`/data/projects/gascity-packs/worktrees/normalized-3f91225712f8005e7b62ea43969101c0aa92df53258931f464bdd57cc963f24a-opus`
with `pwd -P` confirmed against it first.

**First verification command** (syntax gate):

```
bash -n gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
```

Observed: **pass** (`SYNTAX OK`); `shellcheck -S warning` on the same file also
returned clean.

**Red side** (the current, unguarded tree — this is the state W1 ships in):

```
bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
```

Observed: **fails, exactly as D4 predicts** — enumerated, not counted:

| Leg | Base (unguarded) | Guarded |
| --- | --- | --- |
| 1 | FAIL (behavioral) | PASS |
| 1b | FAIL (behavioral) | PASS |
| 2 | PASS | PASS |
| 3 | PASS | PASS |
| 4 | FAIL (behavioral) | PASS |
| 5 | FAIL (behavioral) | PASS |
| 6 | FAIL (behavioral) | PASS |
| 7 | FAIL (static) | PASS |
| 8 | PASS | PASS |

**Final proof command** (green side, via the permanent red-control override —
the identical file, byte-unmodified, aimed at a guarded formula built by
splicing the D1 block over base lines `:294-:295`, with `:248-:293` verified
byte-identical by `cmp`):

```
REBASE_GUARD_FORMULA=/tmp/rebase-guard-green/mol-refinery-patrol.toml \
  bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
```

Observed: **pass** — `PASS: all legs passed`, all nine legs green.

**Mutation control** (assertion teeth). Deleting only the skip-arm checkout
exit-check from the guarded formula — leaving every other arm intact — was
observed to red legs **1b** (behaviorally) and **7** (statically) while legs 1,
2, 3, 4, 5, 6 and 8 stayed green. This confirms D4's claim that deleting any
single fail-closed arm goes red statically at leg 7, not only behaviorally.

Environment exercised: **git 2.43.0**, jq 1.7, on Linux. Leg 3's `rc 1`
carve-out is measured on this git and is flagged in-file for re-confirmation
against the CI git (2.52) at fix time. Leg 5 is implemented strictly as
`rc != 0`, with 128 recorded as a comment observation only, per D4's rule that
it must never harden into a third exact-code carve-out.

Scratch artifacts (`/tmp/rebase-guard-green`, `/tmp/rebase-guard-mutant`) are
empirical only and are not part of the deliverable; the guarded formula was
never written into the worktree.

### AC coverage

The six acceptance criteria carried on source anchor `gp-ikbyp`
(`gc.ac_ids`). AC-374-07 (inference-gate repin) is deliberately absent — it
belongs to W2, not to this item.

| ID | Status | Evidence |
| --- | --- | --- |
| AC-374-01 | covered | Legs 4 and 5 — dual-ref force-fetch precedes the decision and fails closed; stale-ref trap with restore/re-run |
| AC-374-02 | covered | Leg 1 on EX-1/EX-2 — SHA equality, merge count 2, source ref unchanged; leg 1b for the checkout-failure STOP |
| AC-374-03 | covered | Leg 6 — probe error STOPs at `errored (status 128)`, no `temp`, rebase unreached, zero mutation |
| AC-374-04 | covered | The red→green measurement itself: legs 1/1b/4/5/6 behavioral red and leg 7 static red on base, all nine green guarded |
| AC-374-05 | covered | Legs 2 and 3 — diverged clean and diverged conflicting both behave as today |
| AC-374-06 | covered | Leg 8 executes halt composition; leg 7 pins the order statically; the `$GC_LOG` oracle asserts zero `bd update` on every STOP path |

## Remaining Risks

- **The suite is red on the current tree by construction.** This is the
  intended test-first state, not a defect, but it means CI on this branch is
  red until W2 (`gp-zcsrt`) lands D1/D2. W2 must land before this branch can be
  green. Recorded here rather than resolved, because narrowing the test to pass
  on the unguarded tree would destroy exactly the discriminating power D4 asks
  for.
- **Leg 3's `rc 1` and leg 6's `status 128`** are the only two exact-code
  assertions. Leg 6's is the shim's own deterministic exit and so is
  version-stable; leg 3's is git's empirically stable rebase-conflict code,
  measured here on git 2.43 only. If CI's git 2.52 ever returns a different
  non-zero code for a conflicting rebase, leg 3 reds. Re-confirm at fix time.
- **The suite carries a hard `jq` dependency**, declared by a one-line harness
  preflight. The halt's wisp-pour pipes its answer through real `jq`
  unconditionally, and `jq` is deliberately not shadowed in the stub PATH so
  the pour-id extraction genuinely parses JSON. A CI image without `jq` fails
  the suite at the preflight with a clear message rather than mis-reporting.
- **Leg 7 pins composition order textually.** Legitimate future reformatting of
  the fence (for example moving the prune fetch off line 1) will red leg 7 even
  if behavior is unchanged. That is the intended backstop against silent
  mangling, but it makes leg 7 the leg most likely to need a deliberate update
  alongside a future formula edit.
- **`lift_block` concatenates all matching fences.** Legs 7's probe-uniqueness
  and sentinel-count assertions close the gap that D4 identifies, but a future
  second fence that contains neither the probe nor the sentinel would still
  concatenate silently. Out of scope for W1; noted as a known bound of the
  lift mechanism.
- The harness reports **per-leg** results and continues past a failing leg so
  the red control can enumerate outcomes, which D4 requires ("enumerated, never
  a count"). Harness-level preconditions (missing `jq`, a failed lift) still
  abort immediately. This is a deliberate departure from the sibling witness
  suites' fail-on-first-assertion style.
