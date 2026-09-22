---
schema: gc.build.implementation-summary.v1
workflow:
  id: gcg--9223372036854774667
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
    - path: beads/gp-w53bs
      hash: bead:gp-w53bs
      ids:
        - AC-374-06
    - path: beads/gp-uqj8a
      hash: bead:gp-uqj8a
  coverage:
    - id: AC-374-06
      status: covered
---

# W4 — file the residual-precision-(b) follow-up family as tracked work

## Summary

Files the residual-precision-(b) family as a tracked work item with a stable
identifier, **`gp-uqj8a`**, and links it from the PR body. This discharges
design verification step 9, which is explicit that "committed prose alone is
not the tracking".

The item is filed as **one family rather than two tickets**, which is the
design's own framing: the deleted-`$BRANCH` park mirror and the repeated
stranded-`temp` checkout-STOP are the same operational class — an assigned,
never-healing STOP sitting head-of-line in the refinery's merge queue — and
they share a root cause in what the issue-374 guard deliberately may not do.

This item files tracking only. It implements neither remedy, widens no STOP
semantics, and does not touch merge-push.

## Intended Behavior

Both members are things the shipped guard deliberately leaves alone, and the
tracked item records *why* so a future reader does not mistake them for
oversights:

- **Member (a), deleted `$BRANCH`.** The step parks and escalates when
  `$TARGET` is missing, precisely because `find-work` re-selects open beads
  assigned to this refinery, so one bad bead blocks every other merge. A
  permanently-deleted `$BRANCH` has that same head-of-line shape but no
  equivalent park: after the guard it fails closed at the tracking-ref fetch
  and stays assigned, which is right for a transient failure and never-healing
  for a permanent one. The hard part of any remedy is discriminating a deleted
  branch from an unreachable origin — both surface as a non-zero fetch, and
  getting it wrong parks beads on a network blip. That constraint is written
  into the item.
- **Member (b), stranded `temp`.** The guard already converts this wedge from
  silent corruption into a loud fail-closed STOP that leaves the stale branch
  exactly as found. That is strictly better but not self-healing, so repeated
  hits are the same assigned head-of-line class.

The item also carries its scope guards forward, because the most likely way for
this follow-up to cause harm is someone "fixing" it inside the guard: the STOP
arms' mutation-free property is pinned by legs 1b, 4 and 6 of the regression
suite, merge-push must not be repaired as a drive-by from the rebase step, and
the `1)` arm's bare checkout is deliberately preserved byte-identical.

## Changed Files

| File | Change |
| --- | --- |
| *(none — no product code by construction)* | This item files tracking only. |
| `…/items/gp-sxr1i/pr-body.md` | Follow-up section now links the tracked item `gp-uqj8a`. |

No commit: this item mutates no repository content. The verified tree remains
`2df2dca710ba79876f335300d9a37abbcb3d6d8b`.

## Verification

Static, both halves of the item's stated verification:

The tracked item exists with a stable identifier —

```
gc bd create "mol-refinery-patrol: assigned never-healing STOP family …" \
  --body-file … --type task -p 2 --external-ref gh-374
gc bd show gp-uqj8a
```

Result: `gp-uqj8a`, type `task`, `[P2 · OPEN]`, `External: gh-374`, description
present. It is a first-class rig-store bead, not prose.

The PR body links it —

```
grep -n 'gp-uqj8a' …/items/gp-sxr1i/pr-body.md
```

Result: matched at line 220, inside the `## Follow-up` section, with the family
framing and scope guards alongside the identifier.

Behavioural: none, by construction — this item mutates no product code, so
there is nothing to exercise. Recorded explicitly rather than left blank,
because an empty verification section on a filing-only item is otherwise
indistinguishable from an unverified one.

| ID | Status |
| --- | --- |
| AC-374-06 | covered |

AC-374-06's trace here is by derivation rather than direct statement, as the
decomposition records: the design places this family under its STOP-routing
residuals, which is AC-374-06's scope (guard composition and error routing).
The basis is stated rather than implied.

## Remaining Risks

**`pr-body.md`'s digest moved, by design.** W3's summary cites the artifact at
`sha256:9927ae7e63b12223dea3a8bc3481e4f2520b9040442d5202affbce1ef02adabc`, its
value before this item added the follow-up link. It is now
`sha256:1ae5612e0c7fe0a4c70210b64d8132dc559e30e01af25730255f2b00824c3c25`. That
change is exactly what step 9 asks for — the PR body must link the tracked item
— but it does mean W3's recorded digest is the pre-link one. Flagged so a
reviewer comparing the two does not read it as drift.

**The tracked item is unassigned and unrouted.** That is deliberate for a
directed follow-up: it should be triaged and prioritised against other work
rather than pre-assigned by the item that filed it. The consequence is that it
will not be picked up by any pool worker until someone routes it, which is the
intended behaviour for a follow-up and not a defect — but it does mean filing
alone does not schedule the work.

**Neither member is fixed by this PR, and both remain live in production.** The
guard improves member (b)'s failure mode from silent to loud, and leaves member
(a) exactly as it was. A rig whose source branch is deleted permanently will
still accumulate a recurring assigned STOP until the follow-up lands.
