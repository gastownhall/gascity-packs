---
schema: gc.build.review-fixes.v1
workflow:
  id: gcg--9223372036854775805
  formula: workflows-build-from-convoy
methodology:
  pack: workflows
  name: build-from-review-base
producer:
  formula: build-from-review-base
  stage: apply-review-fixes
  attempt: 1
status: residual
reviewed_head: bb0c9de022cbc81dad012d509535d2feb766f251
fix_commit: 6780afd401c573f614dc6303c728ce3909a4be6b
fix_head: 6780afd401c573f614dc6303c728ce3909a4be6b
residual:
  blocker: 0
  major: 0
  minor: 1
  nit: 0
trace:
  upstream:
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/terra/review-report.md
      hash: sha256:9c2d4ac1da755d1601fbbdc07c25558b49f2bcded684ba1b4872d485953aa836
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work-contract.json
      hash: sha256:04d51caeeb64a121224cab4ed2a331b11b17f864ae437041a684306e27ba9616
      ids:
        - AC-374-01
        - AC-374-02
        - AC-374-03
        - AC-374-04
        - AC-374-05
        - AC-374-06
        - AC-374-07
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/terra/implementation-summary.md
      hash: sha256:2017aa7a920c62f5f617663a51ab43b0fb0ade2b2bbbaeace74d346af77af8cc
    - path: /data/projects/gascity-packs/worktrees/normalized-b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141-terra
      hash: git:6780afd401c573f614dc6303c728ce3909a4be6b
      role: fix-subject
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

# Review fixes — issue 374 terra lane (apply-review-fixes, once)

## Summary

One-pass `review_repair_policy=once` application of the recorded review
findings against worktree
`/data/projects/gascity-packs/worktrees/normalized-b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141-terra`.
`pwd -P` matched; `git rev-parse --git-dir` is not equal to
`--git-common-dir` (this is a linked worktree, not the primary checkout).
Never pushed. Never re-ran the review. Exactly one fixup commit
`6780afd401c573f614dc6303c728ce3909a4be6b` on top of reviewed head
`bb0c9de022cbc81dad012d509535d2feb766f251`.

Gating items (blocker + major) are fixed. Four of five minors were
applied opportunistically. One minor remains deferred to existing beads
`gp-uqj8a` / `gp-kwysx`, so artifact status is `residual` with
`residual_required=0`.

| ID | Status |
| --- | --- |
| AC-374-01 | covered |
| AC-374-02 | covered |
| AC-374-03 | covered |
| AC-374-04 | covered |
| AC-374-05 | covered |
| AC-374-06 | covered |
| AC-374-07 | covered |

## Applied Fixes

- **Severity:** blocker
  **Evidence:** `gastown/tests/test_mol_refinery_patrol_rebase_guard.sh:93,571,581,583,585`; `tests/test_no_bare_bd_commands.py:286`; `.github/workflows/ci.yml:43-44`
  disposition: fixed
  reason: Prefixed the four leg-8 log greps and the one comment with `gc `. `tests/test_no_bare_bd_commands.py` now passes (2 passed). Whole-directory `python3 -m pytest tests -q` is `1 failed, 148 passed, 38 skipped` — the remaining failure is the environmental `test_gastown_lint_findings.py` waiver drift (see Verification), not this change. Base-formula red control still fails legs 1, 1b, 4, 5, 6, 7 and passes 2, 3, 8.

- **Severity:** major
  **Evidence:** `gastown/formulas/mol-refinery-patrol.toml` heading and paragraph formerly at `:991-998` (skip contract `:344-349`)
  disposition: fixed
  reason: Prose-only amendment inside merge-push recovery. Renamed the heading so a skip-path agent does not infer a rebase happened. On `--force-with-lease` failure the paragraph now re-fetches both tracking refs, re-materializes `temp` at the freshly fetched `origin/$BRANCH` **before** probing, re-pushes without rebase when `origin/$TARGET` is still an ancestor, rebases only on probe rc=1, and otherwise aborts without rewriting. The executable `git checkout temp` / `git push origin HEAD:$BRANCH --force-with-lease` block is unchanged. Merge-push's already-merged gate, `--ff-only` tail, and `branch_has_real_change` were not touched.

- **Severity:** minor
  **Evidence:** `gastown/tests/test_mol_refinery_patrol_rebase_guard.sh` leg 8 (was `:577-578`)
  disposition: fixed
  reason: Replaced `grep -q -- '--assignee='` with `grep -Eq -- 'gc bd update TESTBEAD .*--assignee=( |$)'` so the park-clear assertion cannot be satisfied by the successor-wisp assignment.

- **Severity:** minor
  **Evidence:** `gastown/tests/test_mol_refinery_patrol_rebase_guard.sh` leg 1 (after `zero_mutation`)
  disposition: fixed
  reason: Added `! drain_acked || fail "leg1/$kind: drain-ack on the skip success path"` on the skip success path (leg 1). Leg 2 was left alone; a leg-2-only copy is inert on the skip arm.

- **Severity:** minor
  **Evidence:** `.github/workflows/ci.yml:43-44`; recorded verification below
  disposition: fixed
  reason: Ran `python3 -m pytest tests -q` on the touched tree and recorded the result, including the environmental lint-waiver failure, instead of only the inference-gate suite and gastown shell loop.

- **Severity:** minor
  **Evidence:** `gastown/agents/refinery/prompt.template.md:209`, `:264`, `:335`
  disposition: fixed
  reason: Re-pointed the categorical MUST at `:209`, the `mr`/`pr` cheatsheet line at `:264`, and the command-table row at `:335` at the guarded ancestry decision. Touch-only-these-lines in the prompt file; formula primacy is unchanged.

## Residual Findings

- **Severity:** minor
  **Evidence:** `gastown/formulas/mol-refinery-patrol.toml:238-246`, `:253-296`, `:304-308`; beads `gp-uqj8a`, `gp-kwysx`
  disposition: deferred
  reason: A permanently deleted `$BRANCH` still STOPs with drain-ack only and has no park mirror of the missing-`$TARGET` halt. Directed deferral already tracked as `gp-uqj8a` / `gp-kwysx`. Honour their constraints: no rejection-path routing, do not weaken the missing-`$TARGET` halt, do not touch merge-push. Not fixed in this change.

## Verification

All commands ran from
`/data/projects/gascity-packs/worktrees/normalized-b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141-terra`
after `pwd -P` confirmed that path. `git diff --check` clean before the
commit.

`git rev-parse HEAD` after the fixup:
`6780afd401c573f614dc6303c728ce3909a4be6b`.

Rebase-guard suite at the fix head (9/9, exit 0):

```
bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
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

Base-formula red control (byte-unmodified test file against
`05031f2c66e080865c379ff799c7369430560a8f`; exit 1; teeth intact):

```
REBASE_GUARD_FORMULA=<base>/gastown/formulas/mol-refinery-patrol.toml \
  bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
leg 1 FAIL, 1b FAIL, 2 PASS, 3 PASS, 4 FAIL, 5 FAIL, 6 FAIL, 7 FAIL, 8 PASS
```

Inference gate:

```
PYTHONPATH=/home/ubuntu/.local/lib/python3.12/site-packages \
  python3 -m pytest tests/test_gascity_pack_inference_gate.py tests/test_no_bare_bd_commands.py -q
91 passed in 10.08s
```

CI Python step equivalent (whole `tests` directory):

```
PYTHONPATH=/home/ubuntu/.local/lib/python3.12/site-packages \
  python3 -m pytest tests -q
1 failed, 148 passed, 38 skipped, 10 subtests passed in 25.30s
```

The one remaining failure is
`tests/test_gastown_lint_findings.py::GastownLintFindingsTest::test_every_universal_waiver_entry_is_still_reported`
against the locally resolved `gc` (named_session pool-agent waivers no
longer reported). This is the environmental failure named in the
synthesis Calibration section. It does not affect CI's Python step:
`ci.yml:43-44` has no `gc` on `PATH` yet, so that test self-skips. It is
gated separately at `ci.yml:84` with `GC_TEST_BIN` set. At the reviewed
head this directory was `2 failed, 147 passed`; this change removed the
bare-`bd` failure (now 148 passed) and left only the environmental one.

Full gastown shell loop (seven files, all pass):

```
for t in gastown/tests/test_*.sh; do bash "$t"; done
```

Out of confinement (not a residual of this pass): the lease-failure
recovery still spends `--force-with-lease` on genuinely diverged shapes
where `temp` was produced by a real rebase. The review directed that
pre-existing defect into its own bead, not this change.
