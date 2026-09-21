---
schema: gc.build.implementation-summary.v1
workflow:
  id: gcg--9223372036854775475
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
    - path: beads/gp-zyrv0
      hash: bead:gp-zyrv0
      role: source-anchor
      ids:
        - AC-374-06
    - path: beads/gp-2rn1y
      hash: bead:gp-2rn1y
      role: filed-follow-up-tracking
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work-contract.json
      hash: sha256:04d51caeeb64a121224cab4ed2a331b11b17f864ae437041a684306e27ba9616
      role: work-contract
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/approved-design.md
      hash: sha256:057ad99d6da1db77b8fb68d5e7297b8d988eb7fffa697aea37d1638a32ce9738
      role: approved-plan
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/decompose.md
      hash: sha256:84a9b1833164f4de4c61b8b700d73270a66fb1b5ec146e27ebc3fc58d1a26b5c
      role: decomposition
    - path: .gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/drain-items/2-gp-hptxz/pr-body.md
      hash: sha256:22e5a64f9b36292ed3e2622b41739a7e602562da229e848ea0760e724f764604
      role: derivation-source
    - path: .gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/drain-items/3-gp-zyrv0/pr-body.md
      hash: sha256:981eb12a3c6eb4bf952724e80aa386d5c291d0a4cb65f78cea35faa64d16fe27
      role: pr-body
  coverage:
    - id: AC-374-06
      status: covered
    - id: AC-374-01
      status: not_applicable
      rationale: Owned by W1 (gp-yzkjn) and W2 (gp-n7z1g); W4 files tracking and mutates no product code.
    - id: AC-374-02
      status: not_applicable
      rationale: Owned by W1 (gp-yzkjn) and W2 (gp-n7z1g); W4 files tracking and mutates no product code.
    - id: AC-374-03
      status: not_applicable
      rationale: Owned by W1 (gp-yzkjn) and W2 (gp-n7z1g); W4 files tracking and mutates no product code.
    - id: AC-374-04
      status: not_applicable
      rationale: Owned by W1 (gp-yzkjn) and W3 (gp-hptxz); W4 files tracking and mutates no product code.
    - id: AC-374-05
      status: not_applicable
      rationale: Owned by W1 (gp-yzkjn) and W2 (gp-n7z1g); W4 files tracking and mutates no product code.
    - id: AC-374-07
      status: not_applicable
      rationale: Owned by W2 (gp-n7z1g) and W3 (gp-hptxz); W4 files tracking and mutates no product code.
---

# issue-374 W4 — file the residual-precision-(b) follow-up family as tracked work

## Summary

Drain item 3 (member `gp-rccpu`, source anchor `gp-zyrv0`) of convoy `gp-upuli`,
lane `opus`. Implements approved-design.md "Verification at implementation time"
**step 9** — the only step W3 left open.

The design accepts the residual-precision-(b) risk but requires it to be
*tracked*, in its own words: "committed prose alone is not the tracking." This
item discharges that, and nothing else. It writes no product code by
construction.

The tracked item is **`gp-2rn1y`** — "mol-refinery-patrol: assigned head-of-line
family — deleted-`$BRANCH` park mirror + repeated stranded-`temp` checkout-STOP
(374 follow-up)", P2, open, routed to `human`. W4's PR body
(`3-gp-zyrv0/pr-body.md`) links it and states the constraints the family
inherits from this change.

**The item was adopted, not re-filed, and that was a deliberate call.** `gp-2rn1y`
already existed in the rig store when this item started: it was filed on
2026-09-20 by the `terra` lane's W4 (run `06e7ae92…`, anchor `gp-vh4js`) of this
same pilot run, `issue-374-auto-20260915T000438Z`. Terra's lane has since gone
`blocked` / `retryable: false` (`builder_reconciliation_error`, see
`work/healed-20260921T0600Z/terra/builder-error.json`), but the bead is not lane
state — it is a standalone tracker item in the shared `gascity-packs` store,
routed to `human`, tracked by no convoy, and unaffected by its filing lane's
death.

Beads are global; branches are lane-local. Filing a second bead would have put
two permanently-open P2 items describing the identical family in front of
whoever picks this up — the first one worked, the second left to rot. That
degrades the tracking the design asked for rather than providing it. So W4
verified the existing item against *this* lane's tree (below), adopted it, and
recorded the adoption in the store so the item is no longer attributable only to
a dead lane:

```
normalized.adopted_by_run=3f91225712f8005e7b62ea43969101c0aa92df53258931f464bdd57cc963f24a
normalized.adopted_by_anchor=gp-zyrv0
normalized.adopted_by_lane=opus
```

Terra's `normalized.run_id` was left intact — the adoption keys are additive, and
the bead's description was not touched.

## Intended Behavior

After this item, the AC-374-06 error-routing residual is discharged the way the
design requires: a tracked work item with a stable identifier exists, and the
PR body links it.

`gp-2rn1y` carries one family with two members sharing the same assigned
head-of-line class:

1. **Deleted-`$BRANCH` park mirror.** A permanently-deleted `$BRANCH` makes the
   guard's explicit-refspec fetch exit non-zero forever, so the step STOPs
   fail-closed every cycle without mutating the bead — an assigned,
   never-healing STOP. That is a head-of-line risk by the missing-`$TARGET`
   halt's own rationale, but mirroring the halt's park requires bead mutation on
   an error path, which this contract forbids. Deferred, with its own design
   pass required.
2. **Repeated stranded-`temp` checkout-STOP.** After this change the skip arm's
   checkout is exit-checked, so a `temp` stranded by the pre-existing merge-push
   STOP wedge produces a loud STOP instead of a silently mis-narrated skip —
   correct, but it repeats every cycle on the same bead: operationally the same
   class as member 1.

The item also records what may **not** be done while fixing either member: no
routing of tooling errors through the conflict-rejection path, and no weakening
of the missing-`$TARGET` halt, the guard's fetch/probe ordering, or merge-push's
ff-only tail. Clearing a stale `temp` stays a human/merge-push-side concern, and
the pre-existing stranding sites (`:826-:829`, `:838-:841`) stay out of scope.

Explicitly not done, per the anchor's "Explicitly NOT in scope": neither mirror
was implemented, STOP semantics were not widened, no bead mutation was added to
any error path, and merge-push was not modified.

## Changed Files

No product code, no tests, no formula, no gate — the branch is untouched and the
worktree is clean at `9b89515`, the commit W3 closed on. W4's output is one
tracker mutation plus artifacts:

| Path | Change |
| --- | --- |
| bead `gp-2rn1y` | Additive metadata only: `normalized.adopted_by_run`, `normalized.adopted_by_anchor`, `normalized.adopted_by_lane`. Description, title, status, priority, owner and `normalized.run_id` unchanged. |
| `.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/drain-items/3-gp-zyrv0/pr-body.md` | New. Derived from W3's sealed `2-gp-hptxz/pr-body.md`; the single diff hunk replaces the `<!-- W4 (gp-zyrv0) files that item and links it here. -->` placeholder at `:256` with the tracked-item link and its constraints. |
| `.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/drain-items/3-gp-zyrv0/evidence/tracked-followup-verification.txt` | New. Transcript of the four verification commands below. |
| `.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/drain-items/3-gp-zyrv0/implementation-summary.md` | New. This file. |

W3's `2-gp-hptxz/pr-body.md` was **not** edited in place: W3's summary seals it at
`sha256:22e5a64f…`, and mutating it would have invalidated a recorded hash. W4
therefore carries the lane's PR body forward into its own item directory, which
is now the PR body of record (`gc.implementation.pr_body_path` on `gp-zyrv0`).

## Verification

Both halves the anchor requires. **Static:** the tracked item exists with a
stable identifier and the PR body links it. **Behavioral: none** — this item
mutates no product code by construction, so there is nothing to exercise;
completion is evidenced solely by the filed item plus the PR-body link, exactly
as the anchor specifies.

Full transcript: `3-gp-zyrv0/evidence/tracked-followup-verification.txt`.

**First verification command** — the tracked item exists with a stable
identifier:

```
$ gc bd list --status=open --json | jq -r '.[] | select(.id=="gp-2rn1y") | ...'
gp-2rn1y | open | P2 | mol-refinery-patrol: assigned head-of-line family — deleted-$BRANCH park mirror + repeated stranded-temp checkout-STOP (374 follow-up)
```

**PASS** — open, P2, stable id `gp-2rn1y`.

Second, the PR body links it:

```
$ grep -n 'gp-2rn1y' .../drain-items/3-gp-zyrv0/pr-body.md
256:**Tracked as `gp-2rn1y`** — "mol-refinery-patrol: assigned head-of-line family —
```

**PASS.**

Third, no product code was mutated, and the derivation is confined:

```
$ git -C worktrees/normalized-3f912257…-opus status --porcelain
                       # empty — clean
$ git -C worktrees/normalized-3f912257…-opus rev-parse HEAD
9b8951553f9e4c57effb84865cf2a1f282a467a1
$ diff 2-gp-hptxz/pr-body.md 3-gp-zyrv0/pr-body.md | grep -E '^[0-9]'
256c256,276     # the placeholder hunk, and only it
$ sha256sum 2-gp-hptxz/pr-body.md
22e5a64f9b36292ed3e2622b41739a7e602562da229e848ea0760e724f764604   # W3 seal intact
```

**PASS** on all three.

Fourth, the adopted item was checked against *this* lane's tree rather than
trusted from terra's. Every claim in `gp-2rn1y` holds on `9b89515`:

| `gp-2rn1y` claim | Site on this branch | Result |
| --- | --- | --- |
| Guard force-fetches both refs with explicit refspecs and STOPs fail-closed, no bead mutation | `:304` fetch, `:305-:307` STOP (echo + `gc runtime drain-ack` + `exit 1`) | PASS |
| A deleted `$BRANCH` therefore STOPs forever with the bead left assigned | same arm; no `gc bd update` on any guard path | PASS |
| Skip-arm checkout is exit-checked and STOPs on a stranded `temp` instead of consuming it | `:322` checkout, `:323-:325` STOP | PASS |
| The halt it mirrors parks: assignee cleared, `gc.routed_to=human`, `halt_reason=target_branch_missing`, mayor escalation, next wisp poured | halt `:249-:297` (`--assignee=""`, both `--set-metadata`, `gc mail send mayor/`, `gc bd mol wisp`) | PASS |

**Final proof command** — the artifact validator this stage is gated by, run
locally from the launcher rig root `/data/projects/gascity-packs` before close:

```
$ GC_BEAD_ID=gcg--9223372036854775473 .gc/scripts/checks/build-artifact-valid.sh
build artifact valid: schema=gc.build.implementation-summary.v1 path=/data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/drain-items/3-gp-zyrv0/implementation-summary.md
$ echo $?
0
```

**PASS**, first attempt, no repair round. `gc.implementation.summary_path` was
recorded on workflow root `gcg--9223372036854775475` and read back from the
store before the gate was run, so the gate resolved the real artifact rather
than failing open on a missing key.

| ID | Status | Evidence |
| --- | --- | --- |
| AC-374-06 | covered | The error-routing residual the design accepts is now tracked, not narrated: `gp-2rn1y` exists (open, P2, stable id), carries both members of the family with the no-conflict-routing and no-halt-weakening constraints intact, and is linked from the PR body at `:256`. Verified against this lane's tree — all four `gp-2rn1y` claims re-derived on `9b89515`. |
| AC-374-01 | not_applicable | Owned by W1 (`gp-yzkjn`) and W2 (`gp-n7z1g`); W4 files tracking only and mutates no product code. |
| AC-374-02 | not_applicable | Owned by W1 (`gp-yzkjn`) and W2 (`gp-n7z1g`); W4 files tracking only and mutates no product code. |
| AC-374-03 | not_applicable | Owned by W1 (`gp-yzkjn`) and W2 (`gp-n7z1g`); W4 files tracking only and mutates no product code. |
| AC-374-04 | not_applicable | Owned by W1 (`gp-yzkjn`) and W3 (`gp-hptxz`); W4 files tracking only and mutates no product code. |
| AC-374-05 | not_applicable | Owned by W1 (`gp-yzkjn`) and W2 (`gp-n7z1g`); W4 files tracking only and mutates no product code. |
| AC-374-07 | not_applicable | Owned by W2 (`gp-n7z1g`) and W3 (`gp-hptxz`); W4 files tracking only and mutates no product code. |

## Remaining Risks

- **The adoption is the reviewable decision in this item.** If the intended
  semantics are that each lane must file its own tracker bead, then the correct
  output was a second bead and this item under-delivered by one `gc bd create`.
  The call was made on the ground that beads are shared-store state while
  branches are lane-local, so duplicating would degrade the tracking the design
  asked for. It is cheap to reverse in either direction: file a fresh bead and
  repoint `:256`, or drop the three `normalized.adopted_by_*` keys. Flagged here
  rather than buried because a reviewer diffing lanes will see terra filed and
  opus did not.
- **`gp-2rn1y` is routed to `human` with no owner and no convoy tracking it.**
  That is what "tracked" means here — it is in the store and linked from the PR
  body — but nothing schedules it. If the follow-up needs a scheduled owner, that
  is a separate act of triage, outside this item's "files tracking; it does not
  implement either mirror" scope.
- **The PR body of record moved directories.** The lane's current PR body is
  `3-gp-zyrv0/pr-body.md`, not the `2-gp-hptxz/` copy W3 recorded. Both are on
  `gp-*` anchors as `gc.implementation.pr_body_path`; anything that reads "the"
  PR body by globbing `drain-items/*/pr-body.md` will find two and must take the
  highest item index. The alternative — editing W3's copy in place — would have
  broken W3's recorded `sha256:22e5a64f…`, which is worse.
- **Member-1 claims about a deleted `$BRANCH` are derived, not executed.** That
  the fetch exits non-zero on a deleted branch and the bead stays assigned is
  read off the guard's arms and W3's leg-5 red control, not from a live refinery
  cycle against a genuinely deleted remote branch. The follow-up's own design
  pass should confirm it empirically; nothing in this item depends on it beyond
  the bead's prose.
- **No behavioral coverage, by construction.** Per the anchor, completion rests
  entirely on the filed item plus the link. If `gp-2rn1y` is later closed,
  retitled or deleted, the PR body's `:256` link silently goes stale — no test
  guards it.
