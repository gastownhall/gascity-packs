This is the `build-from-review-base` apply-review-fixes stage. It runs only
under `review_repair_policy=once` and applies the recorded review findings in
exactly one pass; it must never loop and never re-run the review.

Inputs:

- review_mode: {{review_mode}}
- interaction_mode: {{interaction_mode}}
- review_repair_policy: {{review_repair_policy}}
- implementation_target: {{implementation_target}}
- artifact_root: {{artifact_root}}

Read from the workflow root metadata: `gc.build.review_report_path`,
`gc.build.review_verdict`, the optional `gc.build.review_synthesis_path` and
`gc.build.review_scorecard_path`, and `gc.build.code_review_context_path`.

Worktree: resolve the implementation worktree from the review context's
`## Implementation Worktrees` section; otherwise resolve the root's
`gc.input_convoy_id` (or the implementation convoy recorded by `prepare-review`)
to its closed source anchor and read that anchor's `work_dir`. `cd` into it,
verify `pwd -P` matches, and refuse to operate on the
primary checkout (`git rev-parse --git-dir` equal to
`git rev-parse --git-common-dir` means this is not a worktree; stop).

Branches:

- Verdict `approved`: do not mutate code. Write the artifact with
  `status: not_needed`.
- `review_mode=report` (any verdict): do not mutate code. Write the artifact
  with `status: skipped` and front matter `reason: report_mode_forbids_mutation`.
- Verdict `blocked`: do not mutate code. Write the artifact with
  `status: blocked`.
- Missing review report or unresolvable worktree: write the artifact with
  `status: blocked` when a path is available, then close with `gc.outcome=fail`,
  `gc.failure_class=review_fix_blocked`, `gc.restart.entrypoint=build-from-review`,
  and `gc.restart.reason=review_report_missing|worktree_unresolvable`.
- Otherwise (verdict `changes_required`, review_mode agent or interactive): fix
  ALL findings with `**Severity:** blocker` or `**Severity:** major`; fix minor
  and nit findings opportunistically. When a finding cites a doc or contract,
  read it first. Run `git diff --check` plus the proof commands named by the
  review report and the implementation summary. Make EXACTLY ONE fixup commit
  `review-fixes: <summary>`; on gated repair attempts (`gc.attempt` greater
  than 1) amend that commit, never add a second commit. Never push. Never
  re-run the review. Never loop.

Artifact: write `<artifact_root>/review-fixes.md` with schema
`gc.build.review-fixes.v1` (required sections `Summary`, `Applied Fixes`,
`Residual Findings`, `Verification`). Use `status: fixed` when every residual
count is zero and `status: residual` otherwise. Front matter also carries
`reviewed_head: <review-subject rev from the report's trace.upstream>`,
`fix_commit: <sha or "">`, `fix_head: <HEAD after fixes>`, and
`residual: {blocker, major, minor, nit}` computed with
`.gc/scripts/review_findings_counts.py findings review-fixes.md --section "Residual Findings"`.
Every finding under `## Residual Findings` is a bullet with
`**Severity:**`, `**Evidence:**`, `disposition: fixed|deferred|disputed`, and a
reason. `trace.upstream` includes the review report with its `sha256:` and
`{path: <worktree>, hash: git:<fix_head>, role: fix-subject}`.

Parser resolution (the same chain every review-slot producer uses): the
rig-installed copy first, then the base pack checkout under the work dir, then
the extending pack's mirror.

```bash
# The severity/scorecard parser: the rig-installed copy first, then the base
# pack checkout under the work dir, then the pack mirror.
COUNTS=".gc/scripts/review_findings_counts.py"
if [ ! -f "$COUNTS" ]; then COUNTS="${GC_WORK_DIR:-.}/gascity/assets/scripts/review_findings_counts.py"; fi
if [ ! -f "$COUNTS" ]; then COUNTS="${PACK_ROOT:?no review_findings_counts.py on the rig, under GC_WORK_DIR, or PACK_ROOT}/scripts/review_findings_counts.py"; fi
python3 "$COUNTS" findings review-fixes.md --section "Residual Findings"
```

Root metadata to record before closing: `gc.build.review_fixes_path`,
`gc.build.review_fixes_sha256`, `gc.build.review_fix_commit`,
`gc.build.review_fix_head`, `gc.build.review_fix_attempts=1` (`0` for
`not_needed`, `skipped`, or `blocked`),
`gc.build.review_residual_findings=blocker=<n>,major=<n>,minor=<n>,nit=<n>`,
`gc.build.review_residual_required=<blocker+major>`, and
`gc.build.review_post_fix_verified=false`. On this step bead record
`code_review.verdict=done` when residual_required is 0, otherwise
`code_review.verdict=iterate`. Close with `gc.outcome=pass` for `not_needed`,
`fixed`, `residual`, and `skipped`; fail only for `blocked`. `repair-review`
remains the single writer of `gc.build.repair_status`.

Artifact validation: this stage is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.review_fixes_path` against schema `gc.build.review-fixes.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.

Do not invoke provider-native subagents or provider-specific task tools.
