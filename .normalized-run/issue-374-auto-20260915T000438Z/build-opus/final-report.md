---
schema: gc.build.final-report.v1
workflow:
  id: gcg--9223372036854774601
  formula: workflows-build-from-convoy
methodology:
  pack: gascity
  name: build-basic
producer:
  formula: workflows-build-from-convoy
  stage: finalize
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
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/review-report.md
      hash: sha256:c13cbf067d5bf2649f759771e96cd9701b1aeae14b3e876af8d38a3559de1bf5
      role: review-report
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

# Final report — issue-374 opus continuation (`workflows-build-from-convoy`)

## Summary

This run started at the **`workflows-build-from-convoy`** continuation
entrypoint (`gc.build.entrypoint=workflows-build-from-convoy`), bound to
implementation convoy `gp-upuli`. Because that entrypoint resumes from an
already-approved design, the upstream producer stages were **skipped as
already satisfied by existing approved artifacts**:

| Upstream stage | Why skipped | Artifact consumed |
| --- | --- | --- |
| requirements | approved work contract already existed | `work-contract.json` (`04d51cae…`) |
| plan / design | approved design already existed | `work/approved-design.md` (`057ad99d…`) |
| plan review | design-review already returned approve | `work/design-review/result.json` (`ba94b09a…`) |
| decompose | convoy `gp-upuli` was already decomposed | `work/decompose-graph.json` (`d1eeeeff…`) |

The stages this run actually executed: `prepare-convoy` (pass) →
`implement-same-session` (pass; drained 4 convoy items,
`gc.build.implementation_drain_state=succeeded`) → `prepare-review` (pass) →
`review` (pass, verdict **approved**) → `repair-review` (pass,
`gc.build.repair_status=not_needed`) → this `finalize` stage. `publish` is
authorized to no-op: `push=false` and `open_pr=false`.

Implementation evidence is present and hash-stable: the aggregate
implementation summary (`df513444…`) matches the root's recorded
`gc.build.implementation_summary_sha256`, and the review report (`c13cbf06…`)
matches `gc.build.review_report_sha256`. Both were re-hashed at finalize time,
not trusted from metadata.

## Outcome

**Passing terminal outcome.** Every gate the finalize contract requires is
satisfied:

- all prerequisite artifacts exist and re-hash to their recorded digests;
- implementation evidence present, drain state `succeeded`, 4/4 items;
- review verdict `approved` with 0 fix attempts;
- `gc.build.repair_status=not_needed`;
- no drift on bound inputs (recorded by the review stage and re-checked here);
- subject worktree clean at head `9b89515`, base `05031f2c` an ancestor.

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

Implementation subject: branch
`normalized/3f91225712f8005e7b62ea43969101c0aa92df53258931f464bdd57cc963f24a/opus`,
base `05031f2c`, head `9b89515` — two commits, test-first, touching exactly the
three files the approved design names (nine-leg regression suite, formula
rebase guard, inference-gate repin).

**Publish authorization:** none. `push=false`, `open_pr=false`. The branch stays
local; nothing is pushed and no PR is opened by this run.

**Next action:** hand the branch to a human or a follow-on publish run. First CI
contact has not happened yet (see Remaining Risks); the leg-3 conflict-code
assertion should be re-confirmed on CI's git 2.52 at PR time.

## Artifacts

| Role | Path | Digest |
| --- | --- | --- |
| requirements / context | `.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work-contract.json` | `sha256:04d51cae…` |
| approved plan | `…/work/approved-design.md` | `sha256:057ad99d…` |
| plan review | `…/work/design-review/result.json` | `sha256:ba94b09a…` |
| decomposition | `…/work/decompose-graph.json` | `sha256:d1eeeeff…` |
| implementation summary (aggregate) | `…/work/builders/opus/implementation-summary.md` | `sha256:df513444…` |
| review report | `…/work/builders/opus/review-report.md` | `sha256:c13cbf06…` |
| final report (this file) | `…/work/builders/opus/final-report.md` | — |
| implementation convoy | `gp-upuli` (4 items, drain bead `gcg--9223372036854774597`) | — |
| review subject worktree | `worktrees/normalized-3f91225712f8005e7b62ea43969101c0aa92df53258931f464bdd57cc963f24a-opus` | `git:9b89515` |

Per-item drain evidence lives under `…/work/builders/opus/drain-items/`. Those
directories are keyed by **source anchor**, not member id (dirs `2-gp-hptxz`
and `3-gp-zyrv0` correspond to members `gp-rxjes` and `gp-rccpu`); the
aggregate summary carries the mapping.

## Remaining Risks

Carried forward verbatim in substance from the review stage's
`gc.build.review_unresolved_findings`; none blocks this outcome.

1. **Leg-3 exact `rc 1` conflict-code assertion is unverified on CI git.**
   Measured empirically on git 2.43.0; CI runs 2.52, and git documents only
   "non-zero on conflict". Design-sanctioned scoped carve-out, flagged in-file.
   This is the single most likely source of a first-run CI red, and it would
   indict the assertion's spelling, not the guard.
2. **`tests/test_gastown_lint_findings.py::test_every_universal_waiver_entry_is_still_reported`
   fails locally on BOTH the base and fix trees** — pre-existing dev-`gc`
   divergence, not introduced here. Self-skips in CI's `ci.yml:44` sweep and is
   gated separately at `:84` against the installed `gc`.
3. **STOP respawn source is a configuration-and-code trace, not a live refinery
   observation.** The live city instantiates no refinery agent, so no
   STOP→respawn cycle could be watched; the limitation is recorded alongside
   the finding in `2-gp-hptxz/evidence/stop-respawn-source.md`.
4. **One open nit, not fixed:** dead `LEG_ORDER` bookkeeping variable in the new
   suite (`:83`, `:103`). Two dead lines; fold into a future edit rather than
   churning the branch.
5. **No CI signal yet.** With `push=false`/`open_pr=false`, the change has never
   been exercised by CI. Review reproduced the exact `ci.yml:44` command locally
   (1595 passed / 39 skipped, only the pre-existing failure above), which is
   strong but not equivalent.
