---
schema: gc.build.implementation-summary.v1
workflow:
  id: gcg--9223372036854774601
  formula: workflows-build-from-convoy
methodology:
  pack: gascity
  name: build-from-convoy-base
producer:
  formula: workflows-build-from-convoy
  stage: prepare-review
  attempt: 1
status: approved
role: drain-aggregate
trace:
  upstream:
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work-contract.json
      hash: sha256:04d51caeeb64a121224cab4ed2a331b11b17f864ae437041a684306e27ba9616
      role: requirements
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/approved-design.md
      hash: sha256:057ad99d6da1db77b8fb68d5e7297b8d988eb7fffa697aea37d1638a32ce9738
      role: approved-plan
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/design-review/result.json
      role: plan-review
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/decompose-graph.json
      role: decomposition
    - path: .gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/drain-items/0-gp-yzkjn/implementation-summary.md
      hash: sha256:90ca77fca0ad162f871c6a0fbec513f42af1b30216c844d9c9be3e5f397b750f
      role: drain-item-summary
    - path: .gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/drain-items/1-gp-n7z1g/implementation-summary.md
      hash: sha256:52c594575cc5418987c8dfa8d47b27b24fcb274347c5997a3676c097b43ec8c1
      role: drain-item-summary
    - path: .gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/drain-items/2-gp-hptxz/implementation-summary.md
      hash: sha256:85751a6b001c10d007e251ce36ed3e65291907008d5b37fd4413de0d9da632be
      role: drain-item-summary
    - path: .gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/drain-items/3-gp-zyrv0/implementation-summary.md
      hash: sha256:d09afc9f58d0ea5eacc68c7c7369f7d47dcb460f9010863cc70454b64feada64
      role: drain-item-summary
  coverage:
    - id: AC-374-01
      status: covered
      items: [0-gp-yzkjn, 1-gp-n7z1g]
    - id: AC-374-02
      status: covered
      items: [0-gp-yzkjn, 1-gp-n7z1g]
    - id: AC-374-03
      status: covered
      items: [0-gp-yzkjn, 1-gp-n7z1g]
    - id: AC-374-04
      status: covered
      items: [0-gp-yzkjn, 2-gp-hptxz]
    - id: AC-374-05
      status: covered
      items: [0-gp-yzkjn, 1-gp-n7z1g]
    - id: AC-374-06
      status: covered
      items: [0-gp-yzkjn, 1-gp-n7z1g, 2-gp-hptxz, 3-gp-zyrv0]
    - id: AC-374-07
      status: covered
      items: [1-gp-n7z1g, 2-gp-hptxz]
---

# issue-374 — implementation evidence for the `opus` lane

This is the drain aggregate written by `workflows-build-from-convoy.prepare-review`.
It exists so the inherited `build-from-review-base` review suffix can consume the
implementation evidence without inspecting drain internals. It adds no new
findings of its own — every claim below is carried from a per-item summary.

## Review subject

- Convoy: `gp-upuli` (implementation convoy, `gc.input_convoy_id`)
- Drain step: `gcg--9223372036854774597`, `gc.drain_state=succeeded`,
  `gc.drain_count=4`, shared context, single lane, `do-work-item`
- Work branch:
  `normalized/3f91225712f8005e7b62ea43969101c0aa92df53258931f464bdd57cc963f24a/opus`
- Worktree:
  `/data/projects/gascity-packs/worktrees/normalized-3f91225712f8005e7b62ea43969101c0aa92df53258931f464bdd57cc963f24a-opus`
  (clean at handoff)
- Base commit: `05031f2`
- Implementation commits on top of base:
  - `8d087e0` test(gastown): regression test for the mol-refinery-patrol rebase-skip guard (W1)
  - `9b89515` fix(gastown): guard the refinery rebase against an already-based source (W2)

W3 and W4 are verification and tracking items by construction and add no commits.

## Drain items

All four items closed `pass`; no item was skipped.

| # | Member | Source anchor | Item root | Design scope | Status | Summary |
|---|--------|---------------|-----------|--------------|--------|---------|
| 0 | `gp-yzkjn` | `gp-ikbyp` | `gcg--9223372036854775499` | D4 — nine-leg witness suite + permanent red control | approved | `drain-items/0-gp-yzkjn/implementation-summary.md` |
| 1 | `gp-n7z1g` | `gp-zcsrt` | `gcg--9223372036854775485` | D1/D2/D3 — formula guard + inference-gate repin, one atomic commit | approved | `drain-items/1-gp-n7z1g/implementation-summary.md` |
| 2 | `gp-rxjes` | `gp-hptxz` | `gcg--9223372036854775480` | Verification steps 3–8 — red control, full sweep, PR-body records | approved | `drain-items/2-gp-hptxz/implementation-summary.md` |
| 3 | `gp-rccpu` | `gp-zyrv0` | `gcg--9223372036854775475` | Verification step 9 — file the residual-precision-(b) follow-up family | approved | `drain-items/3-gp-zyrv0/implementation-summary.md` |

Note for the reviewer: drain-item directory names 2 and 3 are keyed by the
source anchor (`gp-hptxz`, `gp-zyrv0`), not by the convoy member id
(`gp-rxjes`, `gp-rccpu`). The manifest row above is the mapping.

## What was implemented

- **W1 (`0-gp-yzkjn`)** — test-first. Adds
  `gastown/tests/test_mol_refinery_patrol_rebase_guard.sh`, a nine-leg suite over
  the ancestry decision in `mol-refinery-patrol`'s `rebase` step, plus the
  permanent red-control capability. The guard itself is deliberately *not*
  applied in this item, so the suite is expected red on its own commit. The suite
  lifts the step's fenced bash block whole from the shipped TOML (sentinel
  `git checkout -b temp origin/$BRANCH`) rather than transcribing it, so a red is
  behavioral rather than a lift error.
- **W2 (`1-gp-n7z1g`)** — D1/D2/D3 in a single commit `9b89515`: the formula guard
  and the inference-gate repin land together, so no commit on the branch ever
  carries the guard without the pins that protect it (AC-374-07, honoured
  literally). This turns W1's suite green — all nine legs pass.
- **W3 (`2-gp-hptxz`)** — no source code. Produces the measured evidence and the
  PR body: red-control transcript for both sides
  (`evidence/red-control-base.txt`, `evidence/guarded-fixed-tree.txt`), the gate
  and full-suite sweep (`evidence/gate-pytest.txt`, `evidence/full-suite.txt`,
  `evidence/full-suite-summary.txt`), the pinned-literal site enumeration
  (`evidence/pin-site-enumeration.txt`), the measured no-errexit assumption
  (`evidence/errexit-assumption.txt`), and the verified STOP respawn source
  (`evidence/stop-respawn-source.md`), which replaces the design's
  repo-evidence-only assertion. Everything came back green and the red control
  reproduced D4's predicted per-leg reds exactly. Two findings sharpen the design
  rather than confirm it; both are recorded in `2-gp-hptxz/pr-body.md` and under
  that item's Remaining Risks.
- **W4 (`3-gp-zyrv0`)** — no product code. Discharges the design's requirement
  that the residual-precision-(b) risk be *tracked*. The tracked item is
  **`gp-2rn1y`** (P2, open, routed to `human`). It was **adopted, not re-filed**:
  the bead already existed in the shared `gascity-packs` store, filed 2026-09-20
  by the `terra` lane's W4 of this same pilot run, whose lane has since gone
  blocked. W4 verified it against this lane's tree and stamped
  `normalized.adopted_by_run` / `normalized.adopted_by_anchor` /
  `normalized.adopted_by_lane`, leaving terra's `normalized.run_id` and the
  description intact.

## Review-relevant flags

- The red→green transition is split across W1 and W2 by design. Reviewing W1's
  commit in isolation will show a failing suite; that is the intended shape, not
  a defect.
- W3 recorded two findings that sharpen the design; they are in
  `2-gp-hptxz/pr-body.md`, not silently folded into the code.
- W4's adoption of `gp-2rn1y` is a deliberate deviation from "file a new bead";
  the rationale is in `3-gp-zyrv0/implementation-summary.md`.
- Per-item Remaining Risks sections are authoritative and are not restated here.

## Evidence index

- Per-item summaries and evidence: `drain-items/<n>-<anchor>/`
- PR bodies: `drain-items/2-gp-hptxz/pr-body.md`,
  `drain-items/3-gp-zyrv0/pr-body.md`
- Drain manifest: `gc.drain_manifest.v1` on `gcg--9223372036854774597`
