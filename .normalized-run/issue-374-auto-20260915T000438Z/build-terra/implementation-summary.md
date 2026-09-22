---
schema: gc.build.implementation-summary.v1
role: drain-aggregate
workflow:
  id: gcg--9223372036854775805
  formula: workflows-build-from-convoy
methodology:
  pack: gascity
  name: build-basic
producer:
  formula: workflows-build-from-convoy
  stage: prepare-review
  attempt: 1
status: approved
lane: terra
convoy: gp-j5ugs
trace:
  upstream:
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/terra/items/gp-opi6t/implementation-summary.md
      hash: sha256:fa6b9c8c9a5bfda391178399f1bc2c3d8227ed9c6c037e90df151bf674c04447
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/terra/items/gp-sc2pz/implementation-summary.md
      hash: sha256:75da1e148e1c0166f831f163658d396fb20859534f4e4b7a4a0a112b96c2297e
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/terra/items/gp-2y2nd/implementation-summary.md
      hash: sha256:4c9776be156e6045d2eacc512b984134ffa824629d4f5a94545a3477cbf831b9
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/terra/items/gp-sc2pz/pr-body.md
      hash: sha256:fdfb77ab3621628372fb24fb91aa269080fdd80526023f2a58d8e3f80e60e32f
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/terra/items/gp-2y2nd/pr-body.md
      hash: sha256:c00e87b0937f1c9365aa3c3930ba2431162ffc73073fad0625e86aa0ebdbeda5
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/terra/items/gp-sc2pz/evidence/stop-respawn-source.md
      hash: sha256:b594afceff2e805ee219524ab1945bfbb61c1ee267ee7be15e2b95b65c03588b
    - path: beads/gp-rtbrt
      hash: bead:gp-rtbrt
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work-contract.json
      hash: sha256:04d51caeeb64a121224cab4ed2a331b11b17f864ae437041a684306e27ba9616
  coverage:
    - id: AC-374-01
      status: covered
      source: gp-opi6t
    - id: AC-374-02
      status: covered
      source: gp-opi6t
    - id: AC-374-03
      status: covered
      source: gp-opi6t
    - id: AC-374-04
      status: covered
      source: gp-sc2pz
    - id: AC-374-05
      status: covered
      source: gp-opi6t
    - id: AC-374-06
      status: covered
      source: gp-rtbrt, gp-opi6t, gp-sc2pz, gp-2y2nd
    - id: AC-374-07
      status: covered
      source: gp-opi6t, gp-sc2pz
---

# Drain aggregate — issue-374 terra lane (convoy `gp-j5ugs`)

This file is the **aggregate** view written by
`workflows-build-from-convoy.prepare-review`. It carries the per-item
claims; it does not re-verify them and adds no findings of its own.

## Anchor → artifact map

Convoy `gp-j5ugs` declared four members
(`issue_ids: ["gp-2y2nd","gp-opi6t","gp-rtbrt","gp-sc2pz"]`). The
per-item directories under `items/` are keyed by the **source anchor**.

| Work item | Source anchor | Item root | Outcome | Per-item summary |
| --- | --- | --- | --- | --- |
| W1 — test-first regression suite (D4) | `gp-rtbrt` | — | closed, `gc.work_outcome=shipped` | none on disk; see "W1 evidence" below |
| W2 — D1+D2 formula guard + D3 gate repin (atomic) | `gp-opi6t` | `gcg--9223372036854775480` | closed, `gc.work_outcome=shipped` | `items/gp-opi6t/implementation-summary.md` |
| W3 — red control, verification sweep, PR-body records | `gp-sc2pz` | `gcg--9223372036854775475` | closed, `gc.work_outcome=shipped` | `items/gp-sc2pz/implementation-summary.md` |
| W4 — file residual-precision-(b) follow-up family | `gp-2y2nd` | `gcg--9223372036854774630` | closed, `gc.work_outcome=shipped` | `items/gp-2y2nd/implementation-summary.md` |

## Code landed

All four items shared ONE worktree and ONE branch. W3 and W4 are
evidence/tracking-only and produced no commit — that is their designed
shape, not a gap.

- Worktree: `/data/projects/gascity-packs/worktrees/normalized-b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141-terra`
- Branch: `normalized/b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141/terra`
- Base: `05031f2c66e080865c379ff799c7369430560a8f`
- Head: `bb0c9de022cbc81dad012d509535d2feb766f251`
- `83a2525e1a6956292144c1e82c1ba38b7a5e25c5` — W1, test-first suite
- `bb0c9de022cbc81dad012d509535d2feb766f251` — W2, guard + gate repin

## W1 evidence (no per-item summary file)

☠️ W1 (`gp-rtbrt`) and W2 (`gp-opi6t`) both wrote to the shared
aggregate path `implementation-summary.md`; W2's write landed last, so
W1's own prose is not recoverable from disk. W1's claims survive in its
bead close reason and notes, reproduced verbatim:

> W1 D4 regression suite committed test-first (83a2525) ; unguarded red
> and D1-splice green verified.
>
> W1 D4 suite committed test-first as
> `83a2525e1a6956292144c1e82c1ba38b7a5e25c5` in worktree
> `normalized-b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141-terra`.
> Unguarded red profile: fail 1/1b/4/5/6/7, pass 2/3/8. Guarded D1
> splice: all nine pass.

To avoid a second overwrite, W2's summary was **copied** (not moved) to
`items/gp-opi6t/implementation-summary.md` before this aggregate was
written; the byte content is unchanged
(`sha256:fa6b9c8c9a5bfda391178399f1bc2c3d8227ed9c6c037e90df151bf674c04447`).

## Follow-up filed by W4

`gp-kwysx` — open, P2, assignee `human`: deleted-`$BRANCH` park mirror of
the missing-`$TARGET` halt, plus repeated stranded-`temp` checkout-STOP.

## Proof commands claimed by the items

- `bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh` (W1, W2, W3)
- `PYTHONPATH=/home/ubuntu/.local/lib/python3.12/site-packages python3 -m pytest tests/test_gascity_pack_inference_gate.py -q` (W2, W3)

## Residual risks carried forward

Carried from the items, not re-adjudicated here:

- No-errexit execution assumption: a probe rc=1 must fall through to the
  `case`. Status quo at base `:295`.
- Deliberate `1)`-arm bare checkout vs exit-checked `0)` arm; the
  stranded-`temp` wedge is pre-existing and scoped out.
- `BRANCH == TARGET` degeneracy is asserted by design analysis only and
  is exercised by no test leg.
- Line citations inside the per-item summaries are **this-tree** numbers
  and must not be read as `05031f2c` anchors.
- `push=false` / `open_pr=false` for this run — no PR exists; the
  "PR bodies" are records artifacts on disk only.
