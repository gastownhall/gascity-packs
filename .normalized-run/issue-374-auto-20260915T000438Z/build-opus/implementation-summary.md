---
schema: gc.build.implementation-summary.v1
role: drain-aggregate
workflow:
  id: gcg--9223372036854774975
  formula: workflows-build-from-convoy
  step: workflows-build-from-convoy.prepare-review
convoy:
  id: gp-ydg59
  item_count: 4
  drain_policy: same-session
subject:
  branch: normalized/82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e/opus
  work_dir: /data/projects/gascity-packs/worktrees/normalized-82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e-opus
  base_sha: 05031f2c66e080865c379ff799c7369430560a8f
  head_sha: 2df2dca710ba79876f335300d9a37abbcb3d6d8b
  diff_range: 05031f2c66e080865c379ff799c7369430560a8f..HEAD
status: approved
trace:
  upstream:
    - path: items/gp-0k3k0/implementation-summary.md
      hash: sha256:22b7796dab3a495136dea0579e01d399eebc7430398dbf2bd7c0e2ccb9ef2f34
    - path: items/gp-37c93/implementation-summary.md
      hash: sha256:54d65c6c608ed0fecc00bae3b6465df4b18ac708b9f99f682e00816cb996c0b7
    - path: items/gp-sxr1i/implementation-summary.md
      hash: sha256:3c3df78ad9929779145ede46088dca73c3521faf553305ca6b4dd30fa76044b3
    - path: items/gp-w53bs/implementation-summary.md
      hash: sha256:52dedc19d9055ab027e69510107de53b64997c05d0de8b90000a4f906cc26c55
    - path: items/gp-sxr1i/pr-body.md
      hash: sha256:1ae5612e0c7fe0a4c70210b64d8132dc559e30e01af25730255f2b00824c3c25
---

# Implementation aggregate — issue-374 opus builder lane

All four convoy items drained into **one shared worktree** on one branch. There
is no per-item worktree: the directory under `items/` is keyed by the item's
**source anchor id**, not by the convoy member id, and every item's evidence
refers back to the same tree below.

## Item index

| Item dir (source anchor) | Work unit | Commit | Repository content changed |
| --- | --- | --- | --- |
| `items/gp-0k3k0` | W1 — regression suite for the rebase guard | `4fb56420fdc48a5e447b2ca2331de92bd67ed420` | yes |
| `items/gp-37c93` | W2 — guarded ancestry decision + inference-gate repin (atomic) | `2df2dca710ba79876f335300d9a37abbcb3d6d8b` | yes |
| `items/gp-sxr1i` | W3 — red control, verification sweep, PR-body records | none (evidence only) | no |
| `items/gp-w53bs` | W4 — filed the residual-precision-(b) follow-up (`gp-uqj8a`) | none (evidence only) | no |

W1 is red by construction on its own commit; W2 is the commit that turns it
green, and W2 deliberately lands the formula change and the inference-gate
repin together (AC-374-07 forbids shipping one without the other). W3 and W4
mutate no repository content — W3 records the red/green control sweep and W4
appends the follow-up link to `items/gp-sxr1i/pr-body.md`.

## Changed files (`05031f2c..HEAD`, 3 files, +733 / -4)

```
gastown/formulas/mol-refinery-patrol.toml          |  61 +-
gastown/tests/test_mol_refinery_patrol_rebase_guard.sh | 656 +++++++++++++++++++++
scripts/gascity_pack_inference_gate.py             |  20 +
```

## Claims carried from the items

- The `rebase` step of `mol-refinery-patrol.toml` ran an unconditional
  `git rebase origin/$TARGET`, which flattens merge commits and drops recorded
  conflict resolutions when the target is already an ancestor of the source.
  W2 inserts the ancestry guard; the literal `git rebase origin/$TARGET` is
  preserved byte-identical so the existing inference-gate pin still matches.
- W2 adds five fragments to the `mol-refinery-patrol` command-contract tuple in
  `scripts/gascity_pack_inference_gate.py`.
- W3's sweep reports the suite red against the unguarded base and green against
  the fixed tree, per leg.
- `tests/test_gastown_lint_findings.py` fails locally on this branch, but the
  items establish by negative control that it fails identically at base
  `05031f2c` in a detached worktree carrying none of these changes. It is
  pre-existing and local-only, not a defect of this work.
- Leg 3 asserts git's rebase-conflict `rc 1` as a deliberate, commented
  version-sensitive carve-out.

Per-item risk sections are authoritative; read them in the item summaries
rather than relying on this digest.
