---
schema: gc.build.final-report.v1
workflow:
  id: gcg--9223372036854774975
  formula: workflows-build-from-convoy
methodology:
  pack: workflows
  name: expansion-review-pr
producer:
  formula: workflows-build-from-convoy
  stage: finalize
  attempt: 1
status: draft
review:
  report_path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/review-report.md
  report_sha256: 895c515a74c9a0d8b0c64c47b8f68097c6258e3e5198249814805550e92ea18b
  verdict: changes_required
  review_state: reviewed_with_residual_findings
  repair_status: residual
  fix_commit: 4973942f80ff5a55146d688131cf52e776b67e60
  post_fix_verified: false
  residual:
    blocker: 0
    major: 0
    minor: 0
    nit: 1
  scorecard_decision: request_changes
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
      hash: sha256:4fbb7068e648700527f3c035bc6ca815759cb393632ceeaa5ee9be000ec83ec4
      role: decomposition
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/implementation-summary.md
      hash: sha256:2110ba770e0f0d76894c27e89dca21f80caa87474857044f6cc208ae384d9151
      role: implementation-summary
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/review-report.md
      hash: sha256:895c515a74c9a0d8b0c64c47b8f68097c6258e3e5198249814805550e92ea18b
      role: review-report
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/review-fixes.md
      hash: sha256:0a39874dc28c95af27a4c9dcc060e83a858ab170917a27c68f02e1bb3a1c6b3e
      role: review-fixes
    - path: /data/projects/gascity-packs/worktrees/normalized-82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e-opus
      hash: git:4973942f80ff5a55146d688131cf52e776b67e60
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

# Final report — issue-374 opus builder lane (`workflows-build-from-convoy`)

## Summary

This run entered at the **`workflows-build-from-convoy`** continuation
entrypoint, bound to implementation convoy `gp-ydg59` (4 items). That
entrypoint resumes from an already-approved design, so the upstream producer
stages were **skipped because their approved artifacts already existed**:

| Upstream stage | Why skipped | Artifact consumed |
| --- | --- | --- |
| requirements | approved work contract already existed | `work-contract.json` (`04d51cae…`) |
| plan / design | approved design already existed | `work/approved-design.md` (`057ad99d…`) |
| plan review | design-review already returned approve | `work/design-review/result.json` (`ba94b09a…`) |
| decompose | convoy `gp-ydg59` was already decomposed | `work/decompose-graph.json` (`4fbb7068…`) |

Stages this run actually executed: `prepare-convoy` → `implement-same-session`
(4 convoy items drained in one session) → `prepare-review` → `review` →
`apply-review-fixes` → `repair-review` → `finalize` (this stage).

The review returned **`changes_required`** (`blocker=0, major=2, minor=2,
nit=1`; quality scorecard `request_changes`, 837/850). Under
`review_repair_policy=once` exactly one repair pass ran, producing the single
fixup commit `4973942` on branch
`normalized/82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e/opus`.
All blocker/major/minor findings are fixed; one `nit` is deferred. The fixed
tree was **not re-reviewed** (`review_post_fix_verified=false`).

## Outcome

- **Status: candidate** (`gc.build.status=candidate`,
  `gc.build.review_state=reviewed_with_residual_findings`,
  `gc.build.repair_status=residual`).
- **This is not an approval and is not publish authorization.** `push=false`
  and `open_pr=false` for this run; nothing was pushed and no PR was opened.
- Review evidence recorded on the workflow root:
  `gc.build.review_report_path`, `gc.build.review_report_sha256`,
  `gc.build.review_initial_findings=blocker=0,major=2,minor=2,nit=1`,
  `gc.build.review_residual_findings=blocker=0,major=0,minor=0,nit=1`,
  `gc.build.review_residual_required=0`.
- Implementation evidence: `implementation-summary.md` (`2110ba77…`) plus the
  four drained convoy items under `work/builders/opus/items/`.
- Subject head `4973942f80ff5a55146d688131cf52e776b67e60`, base
  `05031f2c66e080865c379ff799c7369430560a8f`, working tree clean.
- **Next action:** a fresh review pass over the fixed head
  (`4973942`) is required before this candidate can become an approval or be
  published. Restart entrypoint for that pass: `build-from-review`.

Requirement coverage (matches the YAML trace above):

| ID | Status |
| --- | --- |
| AC-374-01 | covered |
| AC-374-02 | covered |
| AC-374-03 | covered |
| AC-374-04 | covered |
| AC-374-05 | covered |
| AC-374-06 | covered |
| AC-374-07 | covered |

## Artifacts

| Role | Path | Hash |
| --- | --- | --- |
| requirements | `…/work-contract.json` | `sha256:04d51cae…` |
| approved plan | `…/work/approved-design.md` | `sha256:057ad99d…` |
| plan review | `…/work/design-review/result.json` | `sha256:ba94b09a…` |
| decomposition | `…/work/decompose-graph.json` | `sha256:4fbb7068…` |
| implementation summary | `…/work/builders/opus/implementation-summary.md` | `sha256:2110ba77…` |
| review report | `…/work/builders/opus/review-report.md` | `sha256:895c515a…` |
| review synthesis | `…/.gc/reviews/gcg--9223372036854774975/attempt-1/synthesis.md` | `sha256:ba432975…` |
| quality scorecard | `…/.gc/reviews/gcg--9223372036854774975/attempt-1/quality-scorecard.md` | `sha256:92aec223…` |
| review fixes | `…/work/builders/opus/review-fixes.md` | `sha256:0a39874d…` |
| final report | `…/work/builders/opus/final-report.md` | this file |

Implementation convoy: `gp-ydg59` (4 items). Work dir:
`/data/projects/gascity-packs/worktrees/normalized-82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e-opus`.

## Remaining Risks

`post_fix_verified: false` — the repaired tree at `4973942` was never
re-reviewed, so every "fixed" disposition below is the fixer's own claim and
carries no independent reviewer confirmation. That is the dominant risk on this
candidate.

Residual findings, verbatim from the review-fixes artifact
(`0a39874d…`, `## Residual Findings`), counts `blocker=0, major=0, minor=0,
nit=1`, of which `0` are gating (blocker+major):

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

Additional risk carried forward, recorded here rather than silently dropped:

- The fixer's verification run of `ci.yml:44` reports **1 pre-existing
  failure** alongside 1595 passed / 39 skipped. It predates this diff and was
  not introduced by the fixup commit, but it is unresolved on this candidate.
- `gc.build.implementation-summary.v1` validation of
  `implementation-summary.md` fails on missing front-matter fields
  (`methodology.pack`, `methodology.name`, `producer.formula`,
  `producer.stage`, `producer.attempt`). Pre-existing, outside this stage's
  scope, and will block any later stage gated on that schema.
