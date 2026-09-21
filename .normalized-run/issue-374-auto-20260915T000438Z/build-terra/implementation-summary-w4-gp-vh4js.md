---
schema: gc.build.implementation-summary.v1
workflow:
  id: gcg--9223372036854775188
  formula: do-work-item
methodology:
  pack: gascity
  name: build-basic
producer:
  formula: do-work-item
  stage: implement-item
  attempt: 1
status: approved
trace:
  upstream:
    - path: beads/gcg--9223372036854775188
      hash: bead:gcg--9223372036854775188
      role: source-anchor
      ids:
        - AC-374-06
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work-contract.json
      hash: sha256:04d51caeeb64a121224cab4ed2a331b11b17f864ae437041a684306e27ba9616
      role: work-contract
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/approved-design.md
      hash: sha256:057ad99d6da1db77b8fb68d5e7297b8d988eb7fffa697aea37d1638a32ce9738
      role: approved-plan
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/decompose.md
      hash: sha256:84a9b1833164f4de4c61b8b700d73270a66fb1b5ec146e27ebc3fc58d1a26b5c
      role: decomposition
    - path: beads/gp-2rn1y
      hash: bead:gp-2rn1y
      role: filed-follow-up-tracking
  coverage:
    - id: AC-374-06
      status: covered
    - id: AC-374-01
      status: not_applicable
      rationale: Owned by drain items W1 (gp-3zlmh) and W2 (gp-g9s7a); W4 files tracking only and mutates no product code.
    - id: AC-374-02
      status: not_applicable
      rationale: Owned by drain items W1 (gp-3zlmh) and W2 (gp-g9s7a); W4 files tracking only and mutates no product code.
    - id: AC-374-03
      status: not_applicable
      rationale: Owned by drain items W1 (gp-3zlmh) and W2 (gp-g9s7a); W4 files tracking only and mutates no product code.
    - id: AC-374-04
      status: not_applicable
      rationale: Owned by drain items W1 (gp-3zlmh) and W3 (gp-yk0ku); W4 files tracking only and mutates no product code.
    - id: AC-374-05
      status: not_applicable
      rationale: Owned by drain items W1 (gp-3zlmh) and W2 (gp-g9s7a); W4 files tracking only and mutates no product code.
    - id: AC-374-07
      status: not_applicable
      rationale: Owned by drain items W2 (gp-g9s7a) and W3 (gp-yk0ku); W4 files tracking only and mutates no product code.
---

# Implementation summary — issue-374 W4 (drain item 0, lane terra)

## Summary

Executed drain item 0 (member `gp-vh4js`, item root
`gcg--9223372036854775188`) of the terra implementation lane for run
`issue-374-auto-20260915T000438Z`: **W4 — file the residual-precision-(b)
follow-up family as tracked work.** Filed bead **`gp-2rn1y`** in the rig
work store covering both members of the family the approved design directs
to be tracked rather than narrated: the deleted-`$BRANCH` park mirror of
the missing-`$TARGET` halt, and the repeated stranded-`temp` checkout-STOP
— one family, same assigned head-of-line class, with the design's
constraints carried into the bead (no conflict-rejection routing, no
weakening of the halt/guard/merge-push, no-successor-wisp reconciliation).
Duplicate sweeps for prior coverage of the family returned nothing before
filing. No product code was touched, per the item's definition.

This item's PR-body obligation ("the PR body links it") is discharged
here and by downstream W3: the follow-up bead id for the eventual PR body
is **`gp-2rn1y`**.

A drain-ordering defect was found and escalated (mail to `human`, message
`gcg--9223372036854775182`, after `mayor` and `gc.run-operator` resolved to
no live session): the materialized candidate beads carry every blocks-edge
reversed relative to the approved decomposition (W1 depends_on W2, W2 on W3,
W3 on W4), so the drain executes W4 → W3 → W2 → W1 and item 1 (W3: red
control + verification sweep) would run before W1/W2 write any code, then
`gc.drain_on_item_failure=skip_remaining` would skip the rest. W4 itself is
order-independent (filing only) and completes cleanly in this position.

## Intended Behavior

Per `work/decompose.md` W4 (`gp-zyrv0`, materialized as `gp-vh4js`): file
the residual-precision-(b) family as a tracked work item with a stable
identifier, linked from the PR body. "This item files tracking only; it
implements neither mirror, widens no STOP semantics, and does not touch
merge-push." Behavioral verification is none — the item mutates no product
code by construction; the static obligation is that the tracked item
exists with a stable identifier and is linked.

The filed bead (`gp-2rn1y`) records: member 1 — a permanently deleted
`$BRANCH` under the new guard becomes an assigned, never-healing STOP
(fetch exits non-zero, no bead mutation, find-work re-selects each cycle),
a head-of-line risk by the missing-`$TARGET` halt's own rationale, and the
follow-up is to mirror that halt's park shape (needs bead mutation on an
error path, so it requires its own design pass, including the mid-step
deletion race and transient-vs-permanent fetch failure distinction);
member 2 — the pre-existing merge-push STOP arms strand `temp`, and the
guard's exit-checked skip-arm checkout now STOPs fail-closed on it
repeatedly, the same assigned head-of-line class; the follow-up heals the
stranded branch on the merge-push side without widening the 374 STOP
semantics.

## Changed Files

None. This work item intentionally modifies no repository content: the
implementation worktree
`/data/projects/gascity-packs/worktrees/normalized-06e7ae9267b1e212b5d55ab940d5b69a3df782f3810702fdfe5a7296a37540f9-terra`
was verified clean at base SHA `05031f2c66e080865c379ff799c7369430560a8f`
(`git status --porcelain` empty) after completion. The deliverable is a
bead in the work store (`gp-2rn1y`), not a commit — per the decomposition,
"committed prose alone is not the tracking."

## Verification

First verification command (duplicate sweep, run before filing; empty
result = no prior bead covers the family, so no duplicate):

```console
$ gc bd list --search "stranded temp" --json | jq -r '.[] | "\(.id) | \(.title)"'
$ gc bd list --search "refinery follow-up" --json | jq -r '.[] | "\(.id) | \(.title)"'
$ gc bd list --search "park mirror" --json | jq -r '.[] | "\(.id) | \(.title)"'
$ gc bd list --search "deleted branch" --json | jq -r '.[] | "\(.id) | \(.title)"'
(no output — pass)
```

Filing and existence proof (observed pass — bead resolves with a stable
identifier, `P2 · OPEN`, type task, full family description and constraint
block present):

```console
$ gc bd create "mol-refinery-patrol: assigned head-of-line family — …" -t task -p 2 --body-file … --metadata '{"gc.ac_ids":"AC-374-06", …}' --json
→ "id": "gp-2rn1y", "status": "open"
$ gc bd show gp-2rn1y
○ gp-2rn1y · mol-refinery-patrol: assigned head-of-line family — deleted-$BRANCH park mirror + repeated stranded-temp checkout-STOP (374 follow-up)   [P2 · OPEN]
```

Final proof command (artifact gate, run from the launcher rig root after
recording `gc.implementation.summary_path` on the item root; observed
result: **pass** — `build artifact valid: schema=gc.build.implementation-summary.v1
path=/data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/terra/implementation-summary.md`):

```console
$ cd /data/projects/gascity-packs
$ GC_BEAD_ID=gcg--9223372036854775188 .gc/scripts/checks/build-artifact-valid.sh
build artifact valid: schema=gc.build.implementation-summary.v1 path=…
```

## Remaining Risks

- **Drain order inverted (escalated, unresolved).** The materialized
  convoy's blocks-edges are reversed relative to the approved
  decomposition; the drain will dispatch W3 before W1/W2 exist, fail its
  sweep, and skip the remaining items. Escalated as mail
  `gcg--9223372036854775182` to `human` (no `mayor`/`gc.run-operator`
  session is live in this rig). The fix belongs to the dispatcher/lane
  reconciliation, not to this item.
- **Lane already carrying a reconciliation error.**
  `work/builders/terra/builder-error.json` records
  `builder_reconciliation_error` ("child waiting receipt does not bind this
  wait session", `retryable=false`) from before this session; the drain
  nevertheless wired item 0, which completed normally.
- **PR-body link lands downstream.** With `push=false`/`open_pr=false` no
  PR exists yet; the obligation "PR body links the tracked item" transfers
  to W3 (PR-body records) and the finalize/publish stages. The stable
  identifier to link is `gp-2rn1y` (also recorded in this artifact's trace
  upstream as `beads/gp-2rn1y`).
- **Coverage statuses for AC-374-01..05/07 are `not_applicable` to this
  item only** — they are owned by W1–W3 per the approved decomposition;
  this is scoping, not a gap in the overall change.

| ID | Status |
| --- | --- |
| AC-374-01 | not_applicable |
| AC-374-02 | not_applicable |
| AC-374-03 | not_applicable |
| AC-374-04 | not_applicable |
| AC-374-05 | not_applicable |
| AC-374-06 | covered |
| AC-374-07 | not_applicable |
