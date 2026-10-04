# Root cause analysis: builds stall after plan review because it closed with `gc.work_outcome=blocked`

October 3, 2026. Two of ab-003's eight first-pass baseline builds (runs 5 and 8,
both `build-basic`) hung until the harness's one-hour timeout. Gas City
`1.5.0-dev-bb+8ab11cc90`, gascity pack at `37a78e9`.

## Summary

The plan-review worker found real problems with the plan, recorded
`gc.review.verdict=changes_required`, and closed its step with `gc.outcome=pass`
as its prompt requires. Closing was first rejected for a missing
`gc.work_outcome`, so the worker added `gc.work_outcome=blocked` and closed with
`--force`. The workflow treated the step as passed, but both of Gas City's
ready readers deliberately hide any bead whose closed blocker recorded
`gc.work_outcome=blocked`. The decompose work bead therefore never became ready
work, its pool never had demand, no decomposer session ever started, and
nothing reported the contradiction. The build waited silently until it was
killed.

## Evidence

**Exact correlation.** Across every build in ab-001, ab-002 and ab-003 that
closed a plan-review step (50 in all), the two stalled builds are the only ones
whose plan review recorded `gc.work_outcome=blocked`. The other 48 recorded
`shipped` (35), `no-op` (3) or nothing (10), and all of them went on to
decompose and complete.

**Run 5 timeline** (rig store `fi`, city `/var/tmp/gcja-kpqmh55h`):

| Time (UTC) | Event |
| --- | --- |
| 05:00:06 | `gc.review-synthesizer` claims plan review `fi-bzi` |
| 05:00:34 | Worker: the plan rests on a "fabricated premise"; "this is a blocker" |
| 05:00:54 | `gc bd update fi-bzi --set-metadata gc.outcome=pass --set-metadata gc.review.verdict=changes_required` |
| 05:00:59 | `gc bd close fi-bzi` fails: `work-record gate (warn-only): missing gc.work_outcome (want one of shipped\|no-op\|blocked\|abandoned)` and `cannot close fi-bzi: assignee is "jgkr0blwo-wisp-fe8", actor is "fixture--gc__review-synthesizer-1-pool"; reclaim or use --force` |
| 05:01:04 | `gc bd update fi-bzi --set-metadata gc.work_outcome=blocked && gc bd close fi-bzi … --force` |
| 05:01:05 | Store records `fi-bzi` closed. Decompose work bead `fi-hzo` is open, routed to `fixture/gc.task-decomposer`, unassigned, `is_blocked=0`, and listed in the store's `ready_issues` view |
| 05:01:12 → 05:55 | All 110 reconciler cycles record `scale_check_counts = {core.control-dispatcher: 1}`: zero demand for `gc.task-decomposer`, with no partial-read flags. No reconciler record mentions the template at all |
| 05:55 | Harness timeout |

In a good build (ab-003 run 1), the first reconciler cycle after plan review
closed counted `gc.task-decomposer: 1`, and a decomposer session started 8 s
later. Run 8 follows run 5 step for step: the same rejected close, the same
`gc.work_outcome=blocked`, the same zero demand.

**What ruled out the other suspects:**
- A missed `bead.closed` event: run 8 emitted one and still stalled, and good
  run 15 emitted none and still recovered. The controller rebuilds demand at
  least every patrol, so a missed event only delays a wake by seconds.
- Stuck `is_blocked`: `fi-hzo` has `is_blocked=0` in the store.
- Partial reads, a provider marked red, a held runtime name: the reconciler
  trace shows no partial flags and no create attempt for the template.
- Manifold outages: neither stalled build's sessions saw an API error.
  ab-003 run 6 stalled for that reason instead, and is a separate incident.

## Mechanism

- `BdStore.filterReadyByWorkOutcome` (`internal/beads/bdstore.go`, the check
  at :3326) and the caching store's ready path (`caching_store_reads.go:748`)
  drop a ready candidate when a `blocks` dependency is closed with
  `gc.work_outcome=blocked`. `beads.go:614` states the rule. Upstream `main`
  keeps it, pinned by the conformance test
  `ReadyExcludesDependentWhenBlockerClosedAsWorkOutcomeBlocked`. It is
  intended: work closed as blocked should not unblock its dependents.
- The controller's default scale check counts ready, routed, unassigned work
  through those readers (`cmd/gc/build_desired_state.go:1971`, the live ready
  read at :2618–2668), so the vetoed bead contributes no demand.
- The graph.v2 control path advances on `gc.outcome`, which said `pass`. It
  made the decompose control bead live and waited for its work bead to be
  claimed. No component compares `gc.outcome` with `gc.work_outcome`, and a
  vetoed ready candidate writes no event, so the deadlock is invisible.

## Contributing causes

1. **The plan-review prompt never mentions `gc.work_outcome`**
   (`gascity/assets/workflows/build-basic/plan-review.md`). It tells the worker
   both to "treat required changes as blockers for decomposition" and to close
   with `gc.outcome=pass`. When the close gate asked for a work outcome, a
   worker that had just found blockers picked the honest-sounding `blocked`.
2. **The close gate asks for that value at the worst moment.** Its warning
   ("warn-only") lists `blocked` as a valid choice without saying it vetoes
   every dependent. In both builds it came with an assignee/actor mismatch
   (the session bead ID versus the pool name), and that mismatch, not the
   warning, made the close fail and pushed the worker to retry with `--force`.
3. **Two outcome fields can contradict each other silently.** `gc.outcome=pass`
   advances the graph while `gc.work_outcome=blocked` freezes its successors.

## Why it was rare, and who it affects

Plan review only records `blocked` when the review actually finds blocking
problems and the worker hits the rejected close. That happened in 2 of 50 plan
reviews here, both on backlog tasks where the plan made false claims about the
code. Any `build-basic`-derived formula with a plan-review step can hit it,
including the Jev overlay's full `jev-build` route. `jev-build-direct` and
`jev-build-compact` have no plan review and cannot.

## Fixes

**In the gascity pack (small, immediate):**
- `plan-review.md`, and every step prompt that forces `gc.outcome=pass` while
  reporting findings: say exactly which `gc.work_outcome` to set (`no-op` for a
  review that changed nothing, `shipped` with `gc.work_commit` when it edited
  the plan). Also say that `blocked` stops every downstream step and must be
  paired with `gc.outcome=fail`.

**In Gas City core (the durable fix):**
- Make the contradiction impossible or loud. Either reject or flag a close
  where `gc.outcome=pass` and `gc.work_outcome=blocked` disagree, or have the
  graph.v2 control path treat a closed-`blocked` predecessor as a failed step
  so it escalates instead of waiting forever.
- Emit an event or reconciler-trace record when ready work routed to a template
  is vetoed by a blocked blocker, so a stall like this shows up in seconds.
- Fix the close gate's assignee/actor mismatch for pool sessions, so normal
  closes don't need `--force`, and name the downstream effect of `blocked` in
  its warning.

## Not fixed by

PR gastownhall/gascity#6881 (five v1.5 fixes) does not touch this path. Its
closest change, #6860 (emit `bead.closed` for every observed close), addresses
a different symptom. PR #6810 (reconcile keys on controller wake-ups) changes
nothing under the legacy reconciler. Upstream `main` at `2feddeb32` still has
the veto and no pass/blocked consistency check.

## Fixed

All three Gas City causes are fixed in gastownhall/gascity#6881, alongside the
v1.5 fixes from the Jarvis work:

- `2777a85cb` fix(beads): a closed dependency whose step passed
  (`gc.outcome=pass`) satisfies its dependents whatever its `gc.work_outcome`.
  Every store veto and the controller's blocked-dependency predicate use one
  helper, `ReadinessWorkOutcome`.
- `9b021ab5d` fix(bd): a session closing its own claim runs bd under the
  identity the claim recorded, so ordinary closes no longer need `--force`.
- `d16b6a399` fix(api): `gc init`'s Claude readiness probe sees a gateway
  login, so cities like these no longer need `--skip-provider-readiness`.

Validation, with `gc` built from the PR against the build used here:

- **The stall reproduces and is fixed.** [structure-005](../jev-overlay-build/structure-005/)
  (old `gc`) and [structure-006](../jev-overlay-build/structure-006/) (PR `gc`)
  run a stub plan review that closes `pass` + `blocked`. The old binary leaves
  decompose unclaimed until timeout; the PR binary completes in 4.5 minutes.
- **No forced closes.** In two live builds on the PR binary, workers made 30
  closes with no refusals and no `--force`, against 38 closes, 54 refusals and
  8 forced closes on the old binary for the same workload.
- **No readiness skip.** Both live builds passed `gc init` without
  `--skip-provider-readiness`.

The gascity pack's `plan-review.md` is unchanged: with these fixes, the
built-in pack works as it is.
