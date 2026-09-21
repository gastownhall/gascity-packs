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
    - path: beads/gp-hptxz
      hash: bead:gp-hptxz
      ids:
        - AC-374-04
        - AC-374-06
        - AC-374-07
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work-contract.json
      hash: sha256:04d51caeeb64a121224cab4ed2a331b11b17f864ae437041a684306e27ba9616
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/approved-design.md
      hash: sha256:057ad99d6da1db77b8fb68d5e7297b8d988eb7fffa697aea37d1638a32ce9738
    - path: gastown/formulas/mol-refinery-patrol.toml
      hash: sha256:0cf0a3937272c573821f05dbdd46fb2105572f09d600bde46d199505b9a21811
    - path: gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
      hash: git:8d087e08c4d346ed2dfd7e169bc6ccf691cc9d17
    - path: .gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/drain-items/2-gp-hptxz/pr-body.md
      hash: sha256:22e5a64f9b36292ed3e2622b41739a7e602562da229e848ea0760e724f764604
    - path: .gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/drain-items/2-gp-hptxz/evidence/stop-respawn-source.md
      hash: sha256:a5d945d4bc78e44c54f936be6a2ba622996ac8aed7ff2cd67a2c738c7b9e42d3
  coverage:
    - id: AC-374-04
      status: covered
    - id: AC-374-06
      status: covered
    - id: AC-374-07
      status: covered
---

# issue-374 W3 — red control, full verification sweep, and PR-body records

## Summary

Drain item 2 (member `gp-rxjes`, source anchor `gp-hptxz`) of convoy `gp-vcrzk`.
Implements approved-design.md "Verification at implementation time" steps **3-8**.
Design step 9 (filing the residual-precision-(b) follow-up family) is **not** in
scope here — it is W4, `gp-zyrv0`.

This item writes no source code. Its deliverables are the measured evidence for
the W2 guard and the PR body that carries it:

- `pr-body.md` — the PR body, with every step-8 recording.
- `evidence/red-control-base.txt`, `evidence/guarded-fixed-tree.txt` — the
  red-control transcript, both sides.
- `evidence/gate-pytest.txt`, `evidence/full-suite.txt`,
  `evidence/full-suite-summary.txt` — the sweep.
- `evidence/pin-site-enumeration.txt` — every pinned literal with its sites.
- `evidence/errexit-assumption.txt` — the measured no-errexit assumption.
- `evidence/stop-respawn-source.md` — the verified STOP respawn source,
  replacing the design's repo-evidence-only assertion.

Everything W3 was asked to verify came back green, and the red control reproduced
D4's predicted per-leg reds exactly. Two findings sharpen the design rather than
confirm it; both are recorded in `pr-body.md` and under Remaining Risks.

## Intended Behavior

W3 changes no behavior. It establishes, by measurement, that the W2 guard behaves
as D1-D3 specify and that the claims the PR body must carry are true.

**Red control (step 4).** The identical test file, byte-unmodified, aimed at the
unguarded base tree through the `REBASE_GUARD_FORMULA` override — never a
hand-copied formula, never an edit between runs:

```
git worktree add --detach /tmp/issue374-base-05031f2c 05031f2c
REBASE_GUARD_FORMULA=/tmp/issue374-base-05031f2c/gastown/formulas/mol-refinery-patrol.toml \
  bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
```

Per-leg outcomes, enumerated and never counted, exactly as D4 predicts:

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

The base formula was confirmed unguarded before the run (`ANCESTOR_RC` absent).
Because the lift sentinel exists in both trees, the reds are behavioral, not lift
errors; leg 7's red is the static half.

**Pin sites (step 7).** `mol-refinery-patrol` occurs in the gate at `:91` (prose
dict), `:122` (command dict, repinned) and `:823` (`setup_formulas` registry,
unchanged) — enumerated by grep and re-derived, not counted, and the registry
entry is recorded as having moved from its base citation `:790`. Each pinned
literal was grepped against the changed formula and its sites listed
individually: guard fetch `:304`, probe `:315`, capture `:316`, collective STOP
sentence `:305`+`:337`, skip echo `:327`, preserved rebase `:332`.

**Step-8 records.** All four are in `pr-body.md`; two were converted from
assertion to measurement:

- The **no-errexit assumption** is measured on real git return codes rather than
  argued: the shipped idiom captures rc 1 and rc 128 correctly; under `set -e`
  the shell dies at the probe; the prescribed
  `ANCESTOR_RC=0; probe || ANCESTOR_RC=$?` form preserves both; and `|| true`
  collapses rc 1 **and** rc 128 to 0, routing a needed rebase and an unevaluable
  probe into the skip arm.
- The **STOP respawn source** was measured against the live city, replacing the
  design's assertion. See Verification.

The `1)` arm's bare checkout versus the `0)` arm's exit-checked one, and the
confirmation that no guard STOP arm pours a wisp, are recorded with re-derived
line citations.

## Changed Files

| File | Change |
| --- | --- |
| `.gc/normalized-pilot/.../drain-items/2-gp-hptxz/pr-body.md` | new — the PR body with all step-8 recordings |
| `.gc/normalized-pilot/.../drain-items/2-gp-hptxz/evidence/*` | new — red-control (both sides), gate pytest, full-suite, pin-site enumeration, errexit measurement, respawn finding |
| `.gc/normalized-pilot/.../drain-items/2-gp-hptxz/implementation-summary.md` | this artifact |

**No file in the repository worktree was modified by this item**, and no commit
was made: `git status --porcelain` is empty and `HEAD` remains `9b89515` (W2).
That is correct for a verification item — W3 measures the tree W2 shipped, so
changing it would invalidate the measurement. The scratch base worktree
`/tmp/issue374-base-05031f2c` is empirical only and is not part of the
deliverable.

## Verification

All commands were run from the authoritative worktree recorded on the source
anchor,
`/data/projects/gascity-packs/worktrees/normalized-3f91225712f8005e7b62ea43969101c0aa92df53258931f464bdd57cc963f24a-opus`,
with `pwd -P` confirmed equal to it first. The context path
`/data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work-contract.json`
validated: sha256
`04d51caeeb64a121224cab4ed2a331b11b17f864ae437041a684306e27ba9616`, matching
`normalized.contract_sha256` on the member bead.

**First verification command** (design step 3 / the red control's green side):

```
bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
```

Observed: **pass** — `PASS: all legs passed`, all nine legs green.

Then, in design order:

| Step | Command | Observed |
| --- | --- | --- |
| 4 | red control via `REBASE_GUARD_FORMULA` at `05031f2c` | **fails as predicted** — legs 1/1b/4/5/6 behavioral, leg 7 static, legs 2/3/8 green (rc 1) |
| 5 | `python3 -m pytest tests/test_gascity_pack_inference_gate.py -q` | **pass** — `89 passed` |
| 6 | `for t in gastown/tests/test_*.sh; do bash "$t"; done` | **green, all seven** — pack assets, theme scripts, rebase guard, witness orphan recovery, polecat churn watcher, polecat push gate, witness heartbeat |
| 7 | every pinned literal grepped, sites enumerated | **all present**, sites as listed above; prose dict still passes |

**Final proof command** (design step 6, the full suite as CI runs it — the
broadest gate and the one that would catch collateral damage):

```
for t in gastown/tests/test_*.sh; do bash "$t"; done
```

Observed: **pass** — every test green, including the three untouched-area suites
(witness orphan recovery, polecat churn watcher, polecat push gate) and the
witness heartbeat check.

**Verified STOP respawn source** (residual precision (a)), measured against the
live `maintainer-city` Gas City. The answer is neither of the design's two
candidates: it is the city-level `[session_sleep]` restart policy
(`noninteractive = "5m"`) applied by the session reconciler to the refinery's
`wake_mode = "fresh"` session, after which `find-work` re-selects the untouched
work bead. Three plausible-looking paths are provably inert for a guard STOP:
no `formula`-type order exists for this patrol (the city has three, none the
refinery, and the pack ships none); `orphan-sweep` skips the abandoned wisp
because `is_known_agent` matches the configured `<rig>/refinery` agent on its
first test; and `nudge-on-route` never fires because it triggers on
`bead.updated` and the STOP arms mutate nothing — the zero-mutation property
that makes the STOP safe is what makes that recovery path inert. Full derivation
in `evidence/stop-respawn-source.md`, including the limitation below.

Environment: git 2.43.0, Python 3.12, bash 5.2, jq 1.7 on Linux.

### AC coverage

The three acceptance criteria carried on source anchor `gp-hptxz`
(`gc.ac_ids`).

| ID | Status | Evidence |
| --- | --- | --- |
| AC-374-04 | covered | Red-control transcript, both sides, per-leg enumerated: legs 1/1b/4/5/6 behavioral red and leg 7 static red at `05031f2c`, all nine green on the fix. Mechanism (identical file + env override, no edit between runs) and git version recorded in `pr-body.md` |
| AC-374-06 | covered | Composition and error routing confirmed on the shipped tree: halt range byte-identical by hash, no `gc bd mol wisp` pour in any guard arm (only `:277` in the halt), three STOP arms echo + drain-ack + exit with zero `gc bd update`; leg 8 executes halt composition and leg 7 pins order statically; full suite green so untouched areas are unaffected |
| AC-374-07 | covered | Gate pytest green against the changed tree (`89 passed`); every pinned literal grepped with its sites enumerated individually; all three `mol-refinery-patrol` gate sites enumerated with line numbers re-derived (`:91`, `:122`, `:823`, the last moved from `:790`); prose-dict survival confirmed |

## Remaining Risks

- **Leg 3's `rc 1` is still unverified against CI's git.** Everything here was
  measured on git 2.43.0; CI runs 2.52. Git documents only "non-zero on
  conflict", so leg 3 could red on CI while the guard is correct. W3 could not
  close this — it needs a CI run, not a local one — and it is the single most
  likely source of a first-run CI red on this branch. Carried forward
  explicitly rather than silently assumed away.
- **The respawn finding is a configuration-and-code trace, not a live
  observation.** `maintainer-city` does not instantiate the gastown rig agents
  (no `refinery`/`witness`/`polecat` in `gc agent list`; no refinery session in
  `gc session list --state=all`), so no live refinery STOP→respawn cycle could
  be observed. The three exclusions (`orphan-sweep`, `nudge-on-route`, cadence
  order) are config/code facts and hold regardless; the positive
  "5-minute session_sleep restart" claim is inferred from the policy plus the
  agent contract and the formula's own prose, and would be confirmed empirically
  only on a rig that runs the refinery. The design asked for a production-rig
  measurement; this is the closest the available environment allows, and the gap
  is stated rather than papered over.
- **The respawn answer contradicts the design's framing.** The design offered
  "reconciler cadence vs poured wisps"; the measurement shows it is neither, and
  that `orphan-sweep` — the order whose one-line description ("reset beads
  assigned to dead agents") reads as though it would cover this — explicitly
  does not. Anyone reasoning about STOP recovery from that description alone
  will reach the wrong conclusion, which is why the exclusion is recorded with
  the predicate (`is_known_agent` → `agent_exists`) rather than just asserted.
- **No commit and no PR exist for this item.** `open_pr` and `push` are both
  false for this run, so `pr-body.md` is an artifact, not a posted PR body.
  Whoever opens the PR must transcribe it; the line citations in it are
  re-derived against `9b89515` and will drift if the branch is rebased or
  amended before the PR is opened.
- **Step 6 is the local suite, not the CI job.** It runs the same loop CI uses
  over `gastown/tests/test_*.sh`, but CI may also run jobs outside that glob
  (the gate pytest is invoked separately here for that reason). A CI-required
  check outside both is not covered by this sweep.
- **The follow-up family is not yet filed.** Design step 9 belongs to W4
  (`gp-zyrv0`); until it lands, the residual-precision-(b) items
  (deleted-`$BRANCH` park mirror, repeated stranded-`temp` checkout-STOP) exist
  only as prose in `pr-body.md`, which the design explicitly says is not
  tracking. `pr-body.md` carries a placeholder for W4's link.
