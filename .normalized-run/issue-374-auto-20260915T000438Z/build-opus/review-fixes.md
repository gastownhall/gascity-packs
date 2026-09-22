---
schema: gc.build.review-fixes.v1
workflow:
  id: gcg--9223372036854774975
  formula: workflows-build-from-convoy
methodology:
  pack: workflows
  name: expansion-review-pr
producer:
  formula: build-from-review-base
  stage: apply-review-fixes
  attempt: 1
status: residual
reviewed_head: 2df2dca710ba79876f335300d9a37abbcb3d6d8b
fix_commit: 4973942f80ff5a55146d688131cf52e776b67e60
fix_head: 4973942f80ff5a55146d688131cf52e776b67e60
residual:
  blocker: 0
  major: 0
  minor: 0
  nit: 1
trace:
  upstream:
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/review-report.md
      hash: sha256:895c515a74c9a0d8b0c64c47b8f68097c6258e3e5198249814805550e92ea18b
      role: review-report
    - path: /data/projects/gascity-packs/worktrees/normalized-82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e-opus/.gc/reviews/gcg--9223372036854774975/attempt-1/synthesis.md
      hash: sha256:ba432975b668c2e6477650a8cabbdcc679f0dd90d0809efbc7991c14c59a0d2e
    - path: /data/projects/gascity-packs/worktrees/normalized-82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e-opus/.gc/reviews/gcg--9223372036854774975/attempt-1/quality-scorecard.md
      hash: sha256:92aec223d64d2e483b3199d1bc5ba39508753db29501b3764509cb74aa1bdf2b
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/implementation-summary.md
      hash: sha256:2110ba770e0f0d76894c27e89dca21f80caa87474857044f6cc208ae384d9151
    - path: /data/projects/gascity-packs/worktrees/normalized-82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e-opus
      hash: git:4973942f80ff5a55146d688131cf52e776b67e60
      role: fix-subject
  coverage: []
---

# Review Fixes: issue-374 opus builder lane — mol-refinery-patrol rebase guard

## Summary

One repair pass under `review_repair_policy=once` against review verdict
`changes_required` (`blocker=0, major=2, minor=2, nit=1`, scorecard
`request_changes` at 837/850). Both `major` findings are fixed, both `minor`
findings are fixed, and the `nit`'s executable half is fixed. Exactly one fixup
commit, `4973942` (`review-fixes: route the mr lease-failure retry through the
ancestry decision`), on branch
`normalized/82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e/opus`.
Nothing was pushed, the review was not re-run, and no second commit was made.

The two `major` findings were the same defect seen from two surfaces: D2 made
"skip" a first-class success in the `rebase` step, and two pieces of prose
elsewhere in the pack still described the rebase as unconditional. Both were
correct at base and both were made wrong by this diff, so both are repaired
here rather than deferred.

Diff added by this pass: 5 files, +152 / -8.

| File | Finding | Change |
| --- | --- | --- |
| `gastown/formulas/mol-refinery-patrol.toml` | F1, F4 | `mr` lease-failure recovery re-enters the ancestry decision; `:989` heading retitled; single-shell sentence above the guard fence |
| `gastown/agents/refinery/prompt.template.md` | F2 | quick-reference rebase row carries the guarded decision; fetch row marked best-effort; Sequential Rebase Protocol MUST scoped to the diverged case |
| `gastown/tests/test_mol_refinery_patrol_rebase_guard.sh` | F1, F5 | new leg 9 pins the `mr` carve-out; leg 1 runs AC-374-02's named `--ff-only` verification |
| `gastown/tests/test_gastown_pack_assets.sh` | F2 | new formula+prompt pin on the rebase guidance |
| `tests/test_gascity_pack_inference_gate.py` | F3 | `REFINERY_REBASE_GUARD_PINS` protects the five-fragment repin |

## Applied Fixes

- **[major] Contract & Interface Fidelity — the `mr` lease-failure recovery
  contradicted the skip path.** `disposition: fixed`
  **Evidence:** `gastown/formulas/mol-refinery-patrol.toml:989-1015` (was
  `:989`, `:994-996`); pin at
  `gastown/tests/test_mol_refinery_patrol_rebase_guard.sh:617-676` (leg 9).
  The recovery said "STOP, fetch the latest branch, rebase your temp branch
  again, and retry with `--force-with-lease`". On the skip path `temp` is not a
  rebase product — it is `origin/$BRANCH` with its merges intact — so that
  instruction performed the exact flatten the guard exists to prevent and then
  force-pushed it over the source branch. It now re-enters the `rebase` step's
  ancestry decision: re-fetch both tracking refs, **re-materialize `temp` at the
  freshly fetched `origin/$BRANCH` first**, then re-probe — rc=0 keeps `temp`
  unrebased, rc=1 rebases onto `origin/$TARGET`, any other status STOPs without
  mutating bead state. The text states explicitly that this is a step re-entry
  and that `run-tests` re-runs on the re-materialized `temp`, not a push-level
  fixup. The `:989` heading ("Push the **rebased** branch back to origin") was
  false on the skip path and is retitled. Prose only — no `merge-push`
  behaviour change, so the design's "do not repair merge-push as a drive-by"
  boundary holds. Leg 9 is the requested leg-7-style pin: it slices the `mr`
  section out of the formula, pins the carve-out literals, asserts the retired
  instruction is absent, and enforces the load-bearing ordering
  (re-materialize before re-probe) by byte offset so a reflow cannot break it.
  This also discharges codex's nit (c), "no leg aims at the `mr` retry".

- **[major] Architectural Consistency — the prompt published the bare rebase as
  the "Correct command".** `disposition: fixed`
  **Evidence:** `gastown/agents/refinery/prompt.template.md:209-212` and
  `:337-338` (was `:209`, `:334-335`); pin at
  `gastown/tests/test_gastown_pack_assets.sh:604-635`.
  Both cited sites are amended, per the finding's explicit "do not land a
  `:335`-only patch". The quick-reference row now carries the guarded decision
  (probe, rc=0 skips, only rc=1 rebases, any other status STOPs) instead of a
  bare `git rebase origin/$TARGET` under a column header titled "Correct
  command"; the fetch row records that `git fetch --prune origin` is
  best-effort with an unchecked exit and is not what the decision reads. The
  categorical MUST at `:209` is scoped to the diverged case. The new
  `test_refinery_rebase_guidance_matches_the_guarded_step` extends the
  formula+prompt pairing this file already uses: the probe must be present in
  both files, every quick-reference row naming the rebase must name the probe
  in the same row, and the categorical MUST must not return. Scope held to
  `:209`, the two rows, and the pin — the `:336`/`:337` divergences the finding
  calls pre-existing are untouched.

- **[minor] Test Evidence Quality — the inference-gate repin was itself
  unprotected.** `disposition: fixed`
  **Evidence:** `tests/test_gascity_pack_inference_gate.py:1459-1478` and
  `:1500-1504`.
  `REFINERY_REBASE_GUARD_PINS` asserts each of the five guarded-ancestry
  fragments is in `contracts["mol-refinery-patrol"]`, in the shape the file
  already uses for `WITNESS_ORPHAN_GUARD_PINS`. This closes the finding's
  measurement exactly: deleting all five tuple entries previously left the
  suite at 89 passed, and now fails one test. Containment only, deliberately —
  no exactly-once occurrence pin, because F1 legitimately adds a second mention
  of the probe literal to the formula and an occurrence pin would have made the
  two fixes contradict each other.

- **[minor] Behavioral Correctness — the guard fence had no single-shell
  instruction.** `disposition: fixed`
  **Evidence:** `gastown/formulas/mol-refinery-patrol.toml:250-253`.
  One sentence above the fence, matching the merge-state gate's wording at
  `:820` ("evaluate them in one script that shares shell state"): the block runs
  as one script that shares shell state, the probe's status is captured into
  `ANCESTOR_RC` on the very next line, a split at the probe reads `0` in a fresh
  shell and fires the skip arm on a genuinely diverged source, and every STOP
  arm's `exit` must end the step.

- **[nit] Test Evidence Quality (b) — AC-374-02's named verification was not
  executable on the skip path.** `disposition: fixed`
  **Evidence:** `gastown/tests/test_mol_refinery_patrol_rebase_guard.sh:360-367`.
  Leg 2's `merge-base --is-ancestor` one-liner is copied into leg 1, so the AC's
  "downstream `git merge --ff-only` accepts the source" clause runs for the skip
  path it is actually about instead of being entailed by leg 1's SHA-identity
  assertion plus probe rc=0.

- **[nit] Test Evidence Quality (c) — no leg aimed at the `mr` retry.**
  `disposition: fixed`
  **Evidence:** `gastown/tests/test_mol_refinery_patrol_rebase_guard.sh:617-676`.
  Absorbed into F1's required fix, as the finding directed. Leg 9 is that leg.

## Residual Findings

- **Severity:** nit
  **Evidence:** `gastown/tests/test_mol_refinery_patrol_rebase_guard.sh:576-577`
  (leg 7's `[ "$l_prune" -eq 1 ]` line-1 anchor on the prune fetch)
  `disposition: deferred`
  **Reason:** the finding's remedy for part (a) is explicitly conditional —
  "**If** (a) ever fires on a benign edit, relax it to 'first non-comment line'
  rather than deleting the ordering anchor" — and it has not fired. The anchor
  is green on this tree and on all three control trees exercised in this pass.
  Relaxing it now would trade a fail-closed, self-explaining red for a weaker
  anchor with no evidence that the trade is needed, and the finding itself
  records the strict form as "the right side to err on". The finding is
  non-gating (`Gate impact: none`) and is recorded here so the next editor
  reading a red on that line knows it is cosmetic and knows the sanctioned
  relaxation. No code change in this pass.

## Verification

Commands run in the implementation worktree
`/data/projects/gascity-packs/worktrees/normalized-82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e-opus`
at `fix_head` `4973942`.

| Check | Result |
| --- | --- |
| `git diff --check` | clean, no whitespace errors |
| `python3 -c "import tomllib; tomllib.load(...)"` on the formula | parses |
| `bash -n` on both edited shell suites | clean |
| `bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh` | PASS, 10/10 legs |
| `bash gastown/tests/test_gastown_pack_assets.sh` | PASS |
| `python3 -m pytest tests/test_gascity_pack_inference_gate.py -q` | 89 passed |
| `ci.yml:88` loop over `gastown/tests/test_*.sh` | 7/7 ok |
| `ci.yml:44` full Python pack suite | 1595 passed, 39 skipped, 9586 subtests passed, 1 pre-existing failure |

### Proof commands named by the review report and implementation summary

The review report's required fixes name the formula, the prompt, the
pack-assets pin and the inference-gate test; the implementation summary names
the rebase-guard suite (with its red-control capability) and the inference-gate
repin. All are exercised above. Test-side changes were red-controlled rather
than asserted:

- **Leg 9 discriminates.** With only the `mr` lease-failure prose reverted to
  its base wording and the ancestry guard otherwise intact, leg 9 is the **only**
  leg that reds — legs 1, 1b, 2, 3, 4, 5, 6, 7 and 8 stay green. Against the
  fully unguarded base formula (`REBASE_GUARD_FORMULA` pointed at
  `05031f2c:gastown/formulas/mol-refinery-patrol.toml`) it reds together with
  legs 1, 1b, 4, 5, 6 and 7, while the documented green controls (legs 2, 3, 8)
  stay green. The suite's byte-unmodified red-control capability is preserved.
- **The inference-gate pin discriminates.** In a `git archive` lab, removing
  exactly the five tuple element lines and nothing else takes the module from
  89 passed to `1 failed, 88 passed`, failing
  `test_gastown_build_workflow_contract_covers_orchestration_roles` at the
  assertion added here. The finding's measured "89 → 89" gap is closed.
- **Every assertion in the new pack-assets test is witnessed.** Four controls,
  each red with its own message: (A) restoring the bare `| Rebase on target |`
  row; (B) restoring the categorical MUST at `:209`; (C) removing the probe
  literal from the prompt; (D) keeping the guarded row so the probe is still
  present while adding a second, bare rebase row — which isolates the
  unguarded-row counter that controls A and C do not reach. No assertion in the
  new test is a dead pin.

### Pre-existing failures (not introduced by this pass)

- `tests/test_gastown_lint_findings.py::GastownLintFindingsTest::test_every_universal_waiver_entry_is_still_reported`
  fails with 5 pinned `pack.toml` named-session waivers that the local `gc lint`
  no longer reports. Negative control: in a `git archive` lab of base
  `05031f2c`, carrying none of this branch's changes, it fails identically —
  same test, same assertion line (`:264`), same counts (`1 failed, 7 passed, 1
  subtests passed`). Pre-existing, local-only, and unrelated to this change; the
  implementation summary already recorded it.
- `scripts/gascity_pack_inference_gate.py` exits 1 on an environmental
  `gc`/`bd` beads-module mismatch ("gc embeds …@v1.1.1-…, but bd embeds
  …@devel"). Byte-identical at base in the same lab, so it is an environment
  defect, not a pack defect. The gate's pack-contract assertions are covered by
  `tests/test_gascity_pack_inference_gate.py`, which is green.

### Artifact validation — read this before attempting a repair

This artifact **passes** `gc.build.review-fixes.v1`:

```
$ python3 <base-pack>/gascity/assets/scripts/validate_build_artifact.py \
    --schema gc.build.review-fixes.v1 --path review-fixes.md
{"ok": true, "schema": "gc.build.review-fixes.v1"}
```

The gating check `.gc/scripts/checks/build-artifact-valid.sh` may nonetheless
fail with `error: unknown build artifact schema 'gc.build.review-fixes.v1'`.
That is a schema-deployment gap in this environment, **not** a defect in this
artifact, so the standard repair instruction ("read the validator errors from
`gc.attempt_log` and repair the artifact in place") does not apply — there is
nothing in this file to repair, and rewriting it cannot turn the gate green.

Diagnosis, with a control:

- `review-fixes.v1.yaml` is present only in the base pack checkout that supplied
  this stage's `description_file`
  (`…/.gc/cache/repos/f45b403b…/gascity/schemas/build/`).
- It is absent from both schema roots the check can reach: the implementation
  worktree (`<work_dir>/gascity/schemas/build/`) and the rig-installed
  validator's root
  (`/data/projects/gascity-packs-worktrees/build-methodology-packs/gascity/schemas/build/`).
  Both ship only `decomposition`, `final-report`, `implementation-summary`,
  `plan`, `requirements` and `review`.
- Nothing in `.gc/scripts`, `gascity/assets/scripts` or the workflows pack sets
  `GC_BUILD_SCHEMA_ROOTS`, which is the documented way to add schema ids.
- Control: the previous stage's schema `gc.build.review.v1` validates
  `review-report.md` successfully through the *same* worktree validator, because
  `review.v1.yaml` does ship there. The difference is the schema file's
  presence, not the artifact.

Remedy is environmental and outside this stage's scope (this pass is bounded to
the review findings and to exactly one fixup commit): either ship
`review-fixes.v1.yaml` into the rig/worktree schema root alongside `review.v1`,
or set `GC_BUILD_SCHEMA_ROOTS` for the check to the base pack's
`gascity/schemas/build`. Deliberately not done here — adding an unrelated schema
file to the review-fixes commit would widen it past the findings it exists to
apply.

### Residual counts

Computed with the review-slot parser over this file's `## Residual Findings`
section (`review_findings_counts.py findings review-fixes.md --section
"Residual Findings"`), resolved through the documented chain to the pack mirror
at `/data/projects/workflows/scripts/review_findings_counts.py`:

```
blocker=0,major=0,minor=0,nit=1
```

`review_residual_required` (blocker+major) is **0**, so no gating finding
survives this pass. `status: residual` rather than `fixed` because one
non-gating nit is deliberately deferred above.
