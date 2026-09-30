# Intake v4 routing study: protocol

Written 2026-09-30, after designing on the development set and before any Jev
call on the test set.

## Question

Can Jev, reading only the request text, route work to three tiers so that
small changes skip the planning stages, without sending large or risky work
down a shallow path?

- **compact** → `jev-build-compact`: prepare, one implementation drain, the Jev
  review gate. No requirements, plan, plan review, decomposition or summary.
- **direct** → `jev-build-direct`: `jev-build` without the plan and plan review
  stages.
- **full** → `jev-build`.

## Data

- **Development set** (`dev.json`, 74 records): the intake-router spike's 70
  merged `gastownhall/gascity` PRs, already used by that spike, plus the four
  build A/B tasks. Questions v4 and the routing rule were designed on these.
- **Test set** (`fresh.json`, 100 records): the newest eligible PRs merged after
  that spike's snapshot, collected by `collect_fresh.py` with the spike's
  selection and ground-truth rules unchanged. None was seen during design. It is
  scored once.
- **Ground truth** is the spike's proxy: compact is at most 3 files and 80
  changed lines with no risky path; deep is more than 15 files, more than 600
  lines, or a design-doc, API, schema or migration path; the rest is standard.

## Frozen rule (questions v4, `analyze.py` `FROZEN`)

- **compact** when P(size = compact) ≥ 0.8, `spans_modules` ≤ 0.3,
  `hidden_scope` ≤ 0.3, `risky_surface` = none and `needs_design` = no.
- otherwise **direct** when P(needs_design = no) ≥ 0.9, P(size = deep) ≤ 0.1
  and `spans_modules` ≤ 0.5.
- otherwise **full**.

## Pre-registered success criteria on the test set

1. No ground-truth deep change routed compact.
2. At most 5% of ground-truth deep changes routed direct.
3. Compact recall at least 50% of ground-truth compact changes, against the
   current v3 router run on the same set.
4. Standard changes routed compact are reported one by one; they are the
   accepted near-boundary error.

v3 is run on the test set with the rule the router uses today (argmax compact
at confidence ≥ 0.8, risky surface none, no design) for comparison.
