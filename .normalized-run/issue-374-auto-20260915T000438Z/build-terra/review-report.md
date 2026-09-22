---
schema: gc.build.review.v1
workflow:
  id: gcg--9223372036854775805
  formula: workflows-build-from-convoy
methodology:
  pack: workflows
  name: expansion-review-pr
producer:
  formula: expansion-review-pr
  stage: review
  attempt: 1
status: changes_required
trace:
  upstream:
    - path: /data/projects/gascity-packs/worktrees/normalized-b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141-terra/.gc/reviews/gcg--9223372036854775805/attempt-1/claude-review.md
      hash: sha256:275dc86099786bee8ad37a4c916a66fa2a68d9ed80b737fe16a6489ded246320
    - path: /data/projects/gascity-packs/worktrees/normalized-b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141-terra/.gc/reviews/gcg--9223372036854775805/attempt-1/codex-review.md
      hash: sha256:eaf14c4a3df55046dce6d3d6091f878df9e44fbba29fb2c5136f6725744cc6cb
    - path: /data/projects/gascity-packs/worktrees/normalized-b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141-terra/.gc/reviews/gcg--9223372036854775805/attempt-1/gemini-review.md
      hash: sha256:628c71d317bca211f095985997f6d8afa53513c7130c4062c3a7c12ea3ab156c
    - path: /data/projects/gascity-packs/worktrees/normalized-b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141-terra/.gc/reviews/gcg--9223372036854775805/attempt-1/synthesis.md
      hash: sha256:5eab916bdbda80e164ebb38fe1d79996d3dde0a9d75df517eb6ef8195fefcd97
    - path: /data/projects/gascity-packs/worktrees/normalized-b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141-terra/.gc/reviews/gcg--9223372036854775805/attempt-1/quality-scorecard.md
      hash: sha256:57d6a166bd8b237a4a18e01f4b4b8a47b6977c74146f41433fe9b9ea8e0b091e
    - path: beads/gp-j5ugs
      hash: bead:gp-j5ugs
    - path: /data/projects/gascity-packs/worktrees/normalized-b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141-terra
      hash: git:bb0c9de022cbc81dad012d509535d2feb766f251
      role: review-subject
  coverage: []
---

# Review Report: issue 374 — skip refinery rebase when `origin/$TARGET` is already an ancestor (builder lane `terra`)

## Verdict

**Status: changes_required.**

- Quality scorecard decision: `block`; score `649 / 1000`; threshold `850`.
- `New Findings` counts from `synthesis.md`: `blocker=1, major=1, minor=5, nit=0`.
- Approval predicate: not met on either leg — the synthesis carries a blocker
  and a major, and the scorecard decision is `block` with a score below the 850
  threshold.
- All required lanes ran and all required inputs are present
  (`claude-review.md`, `codex-review.md`, `gemini-review.md`, `synthesis.md`,
  `quality-scorecard.md`), so this is not a `blocked` verdict: nothing is
  missing, the review simply requires changes.
- Gating items: the new shell test makes CI's Python step red (blocker), and
  the `mr` lease-failure retry prose re-rebases a skip-path `temp` (major).
  The five minors are carried as explicitly non-gating.

## Findings

### [8] Release Safety — the new test file makes CI's Python step red

- **Severity:** blocker
- **Confidence:** high
- **Source:** claude (reproduced independently in synthesis)
- **Quality dimension:** correctness
- **Gate impact:** blocker
- **Evidence:** `gastown/tests/test_mol_refinery_patrol_rebase_guard.sh:93,571,581,583,585`; `tests/test_no_bare_bd_commands.py:286`; `.github/workflows/ci.yml:43-44`
- **Why it matters:** `.github/workflows/ci.yml:43-44` runs `python3 -m pytest tests …`, which collects `tests/test_no_bare_bd_commands.py::test_shipped_pack_assets_route_beads_commands_through_gc`. Measured at the reviewed head: **1 failed, 1 passed**, with all five violations naming this one new file (it does not exist at base, so base is green for this test). Whole-directory run at head: `2 failed, 147 passed, 38 skipped` — the second failure is environmental (see the synthesis Calibration section).
- **Required fix:** prefix the four leg-8 log greps and the one comment with `gc `. The stub logs `printf 'gc %s\n' "$*"` (test:101), so the log lines already read `gc bd update TESTBEAD …`; the prefixed form is *stronger*, because it now pins that the halt routes through `gc`:
  - `:93` `# to $GC_LOG; \`gc bd show\`/\`gc bd list\` serve canned JSON; …`
  - `:571` `grep -q 'gc bd update TESTBEAD' "$GC_LOG" ||`
  - `:581` `grep -q 'gc bd mol wisp' "$GC_LOG" ||`
  - `:583` `grep -q 'gc bd update STUB-NEXT-WISP' "$GC_LOG" ||`
  - `:585` `grep -q 'gc bd mol burn TESTBEAD' "$GC_LOG" ||`
  Validated three ways in the synthesis: with those five edits applied in a lab, `test_no_bare_bd_commands.py` goes 5 violations → **0** (`2 passed`); the suite is **9/9 green** against the head formula; and the base-formula red control still reproduces **leg-for-leg identically** (1, 1b, 4, 5, 6, 7 red), so the fix does not cost the suite its teeth. Validate the fix by running `python3 -m pytest tests -q`, not only the gate suite and the shell loop.

### [2] Contract & Interface Fidelity — the `mr` lease-failure retry re-rebases a skip-path `temp`

- **Severity:** major
- **Confidence:** high
- **Source:** codex (major) + gemini (minor); stricter severity kept, and measured in synthesis
- **Quality dimension:** correctness
- **Gate impact:** major
- **Evidence:** `gastown/formulas/mol-refinery-patrol.toml:344-349` (skip contract: "do not rebase, amend, or reset"; "merge-push consumes `temp` unchanged") vs `:991-998` (`**1. Push the rebased branch back to origin:**` … "STOP, fetch the latest branch, rebase your temp branch again, and retry with `--force-with-lease`")
- **Why it matters:** measured end to end in a hermetic lab (bare origin, already-based merge-heavy `source`, 2 merge commits): the guard fence skips and leaves `temp` at `origin/source` with **2** merges; a contributor pushes to `source` after our fetch; `git push origin HEAD:source --force-with-lease` is **rejected (stale info)**, rc=1 — correct; the prose retry (`git fetch origin`; `git rebase origin/main`) returns rc=0 and flattens `temp` merges **2 → 0**; the next `git push origin HEAD:source --force-with-lease` returns **rc=0, forced update** — the contributor commit is discarded and `new.txt` is gone from `origin/source`. That is precisely the harm issue 374 exists to remove, re-entered through unchanged prose. This is **not** mitigated as pre-existing: the paragraph is byte-identical at base and untouched by the diff, but at base `temp` was *always* the product of a rebase, so "rebase your temp branch again" was consistent; the skip arm is the state the diff invented in which that same sentence flattens preserved merge topology. Unchanged text newly reachable in a diff-invented state is a regression, so the "blocking would not remove this from `main`" argument is unavailable and the policy's "major in 1-8 without mitigation" clause fires mechanically. `existing_pr` forces this strategy, so the route is first-class.
- **Required fix:** prose only, in the file the diff already touches — make the lease-retry paragraph re-run the ancestry decision instead of commanding a rebase: re-fetch both tracking refs, re-materialize `temp` at `origin/$BRANCH` and re-push when `origin/$TARGET` is still an ancestor of it; re-run `git rebase origin/$TARGET` only on the diverged (probe rc=1) shape; otherwise abort without rewriting. Also rename the `**1. Push the rebased branch back to origin:**` heading so a skip-path agent does not infer that a rebase happened. **Scope instruction:** touch only the `:991-998` paragraph and that heading. Do **not** change merge-push's already-merged gate, the `--ff-only` tail, `branch_has_real_change`, or any executable line of the merge step — the approved design declares merge-push untouched (`approved-design.md:97`), and this remedy stays inside that constraint precisely because it is a prose amendment to the recovery instruction. **Do not apply gemini's wording verbatim without the re-materialize clause:** "retry with the same ancestry decision … skip if already based" leaves the failure mode open unless the retry *re-materializes* `temp` at the freshly fetched `origin/$BRANCH` **before** probing; after the prescribed re-fetch the lease matches, so a stale `temp` pushes successfully — that is the measured mechanism. **Out of confinement, second half (do not fix here):** the clobber itself is not skip-specific — the same lab on a genuinely diverged base shape (legacy rc=1 arm, `temp` produced by a real rebase) also discarded the contributor commit, so "on lease failure, fetch the latest branch and retry with `--force-with-lease`" spends the very protection the flag provides on base shapes as well. That is a pre-existing defect of the recovery prose and belongs in its own bead, not in this change.

### [9] Test Evidence Quality — leg 8's `--assignee=` assertion cannot see the park it certifies

- **Severity:** minor
- **Confidence:** high
- **Source:** claude (reproduced independently in synthesis)
- **Quality dimension:** correctness
- **Gate impact:** minor
- **Evidence:** `gastown/tests/test_mol_refinery_patrol_rebase_guard.sh:577-578`; `gastown/formulas/mol-refinery-patrol.toml:262` (park) vs `:130` (`gc bd update "$NEXT" --assignee="$GC_AGENT"`, the successor-wisp assignment that satisfies the grep)
- **Why it matters:** AC-374-06 names leg 8 as the witness for the park shape, but `grep -q -- '--assignee='` is satisfied by the successor-wisp assignment line. Measured: mutating the park at `:262` to `--assignee="$GC_AGENT"` — defeating the park and leaving the bead selectable, the head-of-line failure the halt exists to prevent — leaves **all 9 legs green**. The halt itself is untouched by this change, so this is a pre-existing coverage gap surfaced by the new witness, not a behavioural regression; hence minor.
- **Required fix:** recommended, not gating — anchor on the park line and the cleared value:
  ```bash
  grep -Eq -- 'gc bd update TESTBEAD .*--assignee=( |$)' "$GC_LOG" ||
      fail "leg8: assignee not cleared (bead left selectable)"
  ```
  Validated in both directions: red on the park-defeating mutant (`FAIL: leg8: assignee not cleared`), green on the shipped formula (9/9), and linter-clean under the blocker's `gc ` prefix (`2 passed`).

### [9] Test Evidence Quality — the success legs cannot see a `drain-ack` on the skip path

- **Severity:** minor
- **Confidence:** high
- **Source:** codex (mechanism measured in synthesis; its remedy corrected there)
- **Quality dimension:** maintainability
- **Gate impact:** minor
- **Evidence:** `gastown/tests/test_mol_refinery_patrol_rebase_guard.sh:140-146` (`zero_mutation` greps `bd (update|close)|workflow`; `drain_acked` greps `runtime drain-ack`), `:288-315` (leg 1), `:351-367` (leg 2)
- **Why it matters:** the STOP legs assert `drain_acked`, but the success legs assert only `zero_mutation`, which cannot match `runtime drain-ack`. Measured: inserting `gc runtime drain-ack` into the skip arm ahead of the `SKIP-REBASE` echo — which would end the patrol after every already-based source, the success-path inverse of a head-of-line stall — leaves **all 9 legs green**.
- **Required fix:** recommended, not gating — add `! drain_acked || fail "leg1/$kind: drain-ack on the skip success path"` after leg 1's `zero_mutation` assertion. **Correction to codex's remedy — leg 1 is the load-bearing site; leg 2's copy is inert.** Measured: with the assertion added to leg 2 only, the skip-arm mutant stays **green** (leg 2 exercises the diverged arm and never reaches the skip arm's code). With it on leg 1: red on the mutant, and 9/9 green on the shipped formula. Adding it to leg 2 as well is harmless defence in depth, but a leg-2-only patch closes this finding while leaving the gap open.

### [9] Test Evidence Quality — the recorded verification never ran what CI runs

- **Severity:** minor
- **Confidence:** high
- **Source:** claude
- **Quality dimension:** correctness
- **Gate impact:** minor
- **Evidence:** `<artifact_root>/review-context.md` §"Inference gate (design step 5)" / §"Full gastown shell suite (design step 6)"; `approved-design.md:550-556`; `.github/workflows/ci.yml:43-44`
- **Why it matters:** the recipe runs `tests/test_gascity_pack_inference_gate.py` plus the gastown shell loop; CI's Python step collects the whole `tests` directory. Every individual claim in the artifacts is true and the tree is still CI-red — that gap is the mechanism by which the blocker shipped, and it recurs on the next gastown test-file addition.
- **Required fix:** recommended, not gating; also a validation condition on the blocker — run `python3 -m pytest tests -q` for touched trees and record the result, noting the environmental failure explicitly rather than absorbing it silently.

### [3] Change Impact / Blast Radius — a permanently deleted `$BRANCH` STOPs without a park mirror

- **Severity:** minor
- **Confidence:** high
- **Source:** codex (filed major/medium; de-escalated in synthesis on measurement + directed deferral)
- **Quality dimension:** correctness
- **Gate impact:** minor
- **Evidence:** `gastown/formulas/mol-refinery-patrol.toml:238-246` (the halt's own head-of-line argument), `:253-296` (park + escalate + pour + burn), `:304-308` (new fetch STOP: drain-ack + exit only); beads `gp-uqj8a`, `gp-kwysx`
- **Why it matters (and why it is not gating):** codex is right that a permanently missing source branch is the same *assigned, never-healing STOP* class as a missing target and gets no park. Three measurements move it off the gate: (1) **it is a directed deferral, tracked twice** — `gp-uqj8a` (open, P2, external `gh-374`, filed per the design's verification step 9) and `gp-kwysx` (open, P2, assignee `human`) both name exactly this family (deleted-`$BRANCH` park mirror **plus** repeated stranded-`temp` checkout-STOP) and both record *why* the guard excluded it: the remedy needs bead mutation on an error path that the issue-374 contract forbids; (2) **it is not a regression** — codex's "previously checkout failure could fall into the conflict/rejection tail and unassign" does not hold at base: measured base leg 5 = `fence rc=0 on a missing source branch`, i.e. the base fence *silently succeeded* with no `temp`, leaving downstream steps to consume a branch that does not exist, so head converts a silent proceed into an explicit fail-closed STOP that leaves the clone clean — a strict improvement whose residual is the missing park; (3) the diff only *removes* candidates from the rebase path, invents no state that reaches the halt, and blocking would leave `main` with the silent variant.
- **Required fix:** none in this change. Leave to `gp-uqj8a`/`gp-kwysx`, honouring their stated constraints (no rejection-path routing, do not weaken the missing-`$TARGET` halt, do not touch merge-push).

### [10] Architectural Consistency — the refinery prompt's rebase guidance still shows the unconditional form

- **Severity:** minor
- **Confidence:** high
- **Source:** gemini (filed nit; widened in synthesis)
- **Quality dimension:** maintainability
- **Gate impact:** none
- **Evidence:** `gastown/agents/refinery/prompt.template.md:335` (`| Rebase on target | \`git rebase origin/$TARGET\` |`), **`:209`** (`**After every merge, main moves. Next branch MUST rebase on new baseline.**`), `:264` ("push the rebased source branch"); the prompt is **not** in the diff (`git diff --name-only` = formula, test, gate)
- **Why it matters:** the pack states formula primacy (`prompt.template.md:188` "The formula IS your brain"), and the point-of-use instruction now lives in the fence, so this is cheatsheet drift rather than a competing recipe — hence gate impact none. But it is a lookup surface an agent can follow back into the flattening.
- **Required fix:** recommended, not gating — re-point both sites at the guarded decision. **Do not land a `:335`-row-only patch:** `:209` carries the same error in categorical MUST form, so a row-only edit closes the finding while leaving the stronger imperative standing. Because the prompt is a fourth file, give any such change an explicit touch-only-these-lines instruction.

## Verification

Quality scorecard summary (`quality-scorecard.md`):

- **Quality Score:** 649 / 1000
- **Decision:** block
- **Threshold:** 850
- **Caps Applied:** behavioral regression (649) — `[8] Release Safety — the new test file makes CI's Python step red` (blocker), evidence `gastown/tests/test_mol_refinery_patrol_rebase_guard.sh:93,571,581,583,585`; `tests/test_no_bare_bd_commands.py:286`; `.github/workflows/ci.yml:43-44`.
- **Dimension Scores:** Correctness and Test Evidence 164/275; Maintainability and Architecture 214/225; Security and Defensive Design 250/250; Readability and Idiom 150/150; Scope Discipline and Review Hygiene 100/100.
- **Required Changes:** `[blocker] [8] Release Safety — the new test file makes CI's Python step red` (prefix the four leg-8 log greps and the one comment with `gc `); `[major] [2] Contract & Interface Fidelity — the `mr` lease-failure retry re-rebases a skip-path `temp`` (re-run the ancestry decision in the lease-retry prose).
- **Non-Gating Follow-Up:** the five minors above — leg 8's `--assignee=` assertion, the missing `drain-ack` witness on the skip success path, the verification that never ran CI's Python step, the deleted-`$BRANCH` park mirror (deferred to `gp-uqj8a`/`gp-kwysx`), and the refinery prompt's unconditional rebase guidance.
- **Scorecard evidence:** measured complexity `status=ok worst_changed cyclomatic=0 cognitive=0`; static checks not run (deterministic ledger gate); test/build evidence as recorded by the reviewers in the synthesis ledger; 0 findings beyond the per-dimension count cap.

Reviewer lanes that ran:

- `claude` — `gascity-packs/gc.design-implementation-reviewer`, `claude-review.md` present.
- `codex` — `gascity-packs/gc.implementation-reviewer`, `codex-review.md` present.
- `gemini` — `gascity-packs/gc.design-test-risk-reviewer`, `gemini-review.md` present.
- Synthesis — `gascity-packs/gc.review-synthesizer`, `synthesis.md` present (decision `request_changes`).
- Quality scorecard — `gascity-packs/gc.implementation-reviewer`, `quality-scorecard.md` present.

Review subject: worktree `/data/projects/gascity-packs/worktrees/normalized-b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141-terra`, branch `normalized/b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141/terra`, diff range `05031f2c66e080865c379ff799c7369430560a8f..bb0c9de022cbc81dad012d509535d2feb766f251`, head `bb0c9de022cbc81dad012d509535d2feb766f251`.

This step normalized the existing lane outputs into one artifact; it re-ran no reviewer, re-judged no code, and mutated nothing in the review worktree.
