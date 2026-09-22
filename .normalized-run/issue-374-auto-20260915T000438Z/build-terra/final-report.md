---
schema: gc.build.final-report.v1
workflow:
  id: gcg--9223372036854775805
  formula: workflows-build-from-convoy
methodology:
  pack: workflows
  name: build-from-review-base
producer:
  formula: build-from-review-base
  stage: finalize
  attempt: 1
status: draft
review:
  report_path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/terra/review-report.md
  report_sha256: 9c2d4ac1da755d1601fbbdc07c25558b49f2bcded684ba1b4872d485953aa836
  verdict: changes_required
  review_state: reviewed_with_residual_findings
  repair_status: residual
  fix_commit: 6780afd401c573f614dc6303c728ce3909a4be6b
  post_fix_verified: false
  residual:
    blocker: 0
    major: 0
    minor: 1
    nit: 0
  scorecard_decision: block
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
      role: plan
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/design-review/result.json
      hash: sha256:ba94b09ae6633749392401289d4783d9395ee060eeb97dbd987f956930b10165
      role: plan-review
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/decompose-graph.json
      hash: sha256:4fbb7068e648700527f3c035bc6ca815759cb393632ceeaa5ee9be000ec83ec4
      role: decomposition
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/terra/implementation-summary.md
      hash: sha256:2017aa7a920c62f5f617663a51ab43b0fb0ade2b2bbbaeace74d346af77af8cc
      role: implementation-evidence
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/terra/review-report.md
      hash: sha256:9c2d4ac1da755d1601fbbdc07c25558b49f2bcded684ba1b4872d485953aa836
      role: review-report
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/terra/review-fixes.md
      hash: sha256:81dc1bf4972e75aa5a78f5759abed813fecd668942267d275275261f5ddf1528
      role: review-fixes
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

# Final report — issue-374 terra lane continuation

## Summary

This run started at continuation entrypoint `build-from-convoy`
(`workflows-build-from-convoy`, root `gcg--9223372036854775805`), taking the
already-decomposed implementation convoy `gp-j5ugs` as its input. Because
approved upstream artifacts already existed on disk, the requirements/context,
design/plan, design-review, and decomposition stages were **skipped** and their
artifacts were consumed as-is:

- requirements/context: `work-contract.json` (AC-374-01 … AC-374-07)
- plan: `work/approved-design.md`
- plan-review: `work/design-review/result.json`
- decomposition: `work/decompose-graph.json`

The stages this run actually executed were: prepare-convoy, the shared drain of
the four convoy items, prepare-review, `review` (agent mode, multi-lane
expansion plus synthesis and quality scorecard), `apply-review-fixes` (one pass
under `review_repair_policy=once`), `repair-review`, and this finalize stage.

The implementation drained cleanly — all four convoy members
(`gp-rtbrt`, `gp-opi6t`, `gp-sc2pz`, `gp-2y2nd`) closed with
`gc.work_outcome=shipped`, sharing one worktree and one branch. The review
returned `changes_required` with `blocker=1, major=1, minor=5, nit=0`. The
single `once`-policy fix pass fixed both gating findings and four of five
minors in exactly one fixup commit
`6780afd401c573f614dc6303c728ce3909a4be6b`, leaving one deferred minor. No
re-review ran after the fix, so the post-fix state is unverified.

| ID | Status |
| --- | --- |
| AC-374-01 | covered |
| AC-374-02 | covered |
| AC-374-03 | covered |
| AC-374-04 | covered |
| AC-374-05 | covered |
| AC-374-06 | covered |
| AC-374-07 | covered |

## Outcome

- Continuation entrypoint: `build-from-convoy`
- Skipped upstream stages (approved artifacts already existed): requirements,
  plan/design, design-review, decomposition
- Implementation convoy: `gp-j5ugs` (4 items, all closed `shipped`)
- Implementation evidence: present (aggregate drain summary, per-item summaries
  under `items/`)
- Review verdict: `changes_required` (agent mode, headless)
- Initial findings: `blocker=1,major=1,minor=5,nit=0`
- Repair policy: `once`; one fix pass; `gc.build.repair_status=residual`
- Review state: `reviewed_with_residual_findings`
- `gc.build.review_post_fix_verified=false`
- Terminal build status: `candidate`
- Publish authorization: **none** (`push=false`, `open_pr=false`; and a
  candidate with residual findings is not an approval and never publish
  authorization)
- Next action: hand the candidate branch
  `normalized/b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141/terra`
  at `6780afd401c573f614dc6303c728ce3909a4be6b` to a fresh review pass (or a
  human) before any publish. The publish stage must no-op.

## Artifacts

| Artifact | Path | Hash |
| --- | --- | --- |
| Requirements / work contract | `.../work-contract.json` | `sha256:04d51cae…9616` |
| Plan | `.../work/approved-design.md` | `sha256:057ad99d…9738` |
| Plan review | `.../work/design-review/result.json` | `sha256:ba94b09a…0165` |
| Decomposition | `.../work/decompose-graph.json` | `sha256:4fbb7068…3ec4` |
| Implementation summary (aggregate) | `.../builders/terra/implementation-summary.md` | `sha256:2017aa7a…8fcc` |
| Review context | `.../builders/terra/review-context.md` | — |
| Review report | `.../builders/terra/review-report.md` | `sha256:9c2d4ac1…a836` |
| Review synthesis | `<worktree>/.gc/reviews/gcg--9223372036854775805/attempt-1/synthesis.md` | `sha256:5eab916b…cd97` |
| Quality scorecard | `<worktree>/.gc/reviews/gcg--9223372036854775805/attempt-1/quality-scorecard.md` | `sha256:57d6a166…b091` |
| Review fixes | `.../builders/terra/review-fixes.md` | `sha256:81dc1bf4…1528` |
| Final report (this file) | `.../builders/terra/final-report.md` | — |

Subject under review: worktree
`/data/projects/gascity-packs/worktrees/normalized-b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141-terra`,
branch
`normalized/b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141/terra`,
diff range
`05031f2c66e080865c379ff799c7369430560a8f..bb0c9de022cbc81dad012d509535d2feb766f251`,
fix head `6780afd401c573f614dc6303c728ce3909a4be6b`. Never pushed.

The normalized-builder receipt at
`.../builders/terra/implementation-receipt.json` does not exist; sealing it is
the publish stage's responsibility, not an input to this stage.

## Remaining Risks

This is a **candidate**, not an approval. `post_fix_verified: false` — the one
fix pass was never re-reviewed, so every applied fix is asserted by the fixer
and unverified by a reviewer.

Residual findings, verbatim from the review-fixes artifact
(`residual: blocker=0, major=0, minor=1, nit=0`; `review_residual_required=0`):

- **Severity:** minor
  **Evidence:** `gastown/formulas/mol-refinery-patrol.toml:238-246`, `:253-296`, `:304-308`; beads `gp-uqj8a`, `gp-kwysx`
  disposition: deferred
  reason: A permanently deleted `$BRANCH` still STOPs with drain-ack only and has no park mirror of the missing-`$TARGET` halt. Directed deferral already tracked as `gp-uqj8a` / `gp-kwysx`. Honour their constraints: no rejection-path routing, do not weaken the missing-`$TARGET` halt, do not touch merge-push. Not fixed in this change.

Additional risk carried forward, not counted as a residual finding by the fix
pass:

- The quality scorecard decision is `block` (score 649). The scorecard was
  produced against the reviewed head `bb0c9de0…`, before the fixup commit, and
  has not been re-run.
- The fixer records an out-of-confinement pre-existing defect: lease-failure
  recovery still spends `--force-with-lease` on genuinely diverged shapes where
  `temp` came from a real rebase. The review directed it into its own bead.
- `tests/test_gastown_lint_findings.py::test_every_universal_waiver_entry_is_still_reported`
  fails locally against the resolved `gc` binary. The fix pass classifies this
  as environmental (CI's Python step at `ci.yml:43-44` has no `gc` on `PATH`, so
  the test self-skips there; it is gated separately at `ci.yml:84`). That
  classification is unverified by a reviewer.
