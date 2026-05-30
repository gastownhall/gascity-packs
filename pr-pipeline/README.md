# PR Pipeline

Author-side and review-side PR discipline distributed as a Gas City pack.

Encodes the planning, blast-radius, scorecard-review, and pre-push gating
workflows that careful contributors run by hand, so any city that imports
this pack gets the same discipline as platform-native formulas and
commands.

## Status

**v0.1.0** — initial release. Ships four formulas and matching wrapper
commands:

| Formula | Command | Purpose |
|---------|---------|---------|
| `mol-pr-start`        | `gc <binding> pr plan <issue>`         | Issue → structured plan with BLOCKING gates |
| `mol-pr-blast-radius` | `gc <binding> pr blast-radius "<scope>"` | Map impact surface (callers, configs, concurrency) |
| `mol-pr-review`       | `gc <binding> pr review <pr-number>`   | Outgoing-PR self-review against an 11-category scorecard |
| `mol-pr-ship`         | `gc <binding> pr ship`                 | Pre-push gate (simplify → review-iterate → contributor check); STOPS at report |

All four are read-only by default for filesystem changes outside their
own output paths. `mol-pr-ship` may modify the diff during simplify and
review-iteration stages; everything else writes only to
`.gc/pr-pipeline/<sub>/`. None of them push or open PRs — those decisions
stay with the caller.

## Sibling pack

`pr-review` (in this same repo) covers the **maintainer-side incoming-PR
review/merge workflow** with `mol-adopt-pr` — a 5-step formula for
adopting contributor PRs (intake → rebase → review → human-gate →
finalize). The two packs are complementary:

- `pr-review` → reviewing PRs that arrive at your repo
- `pr-pipeline` → planning, building, and shipping PRs your city sends out

A city that does both ("we contribute to repos and we accept contributions
from others") imports both. Both packs use the same 11-category scorecard
in their review steps, so feedback shape stays consistent regardless of
direction.

## Usage

In your city's `pack.toml`:

```toml
[imports.pr-pipeline]
source = "../packs/pr-pipeline"   # path; or git URL when published
```

### Plan a PR for an issue

```sh
gc pr-pipeline pr plan 1234 --rig api-server
```

The formula reads the issue, runs BLOCKING gates (competing-PR and
architectural-refactor checks), maps blast radius, checks repo
conventions, writes a structured plan to
`.gc/pr-pipeline/plans/issue-1234.md`, and audits the plan against 19
recurring review findings. **No code is written.**

### Map blast radius for a freeform scope

```sh
gc pr-pipeline pr blast-radius "FuncXYZ in pkg/foo" --rig api-server
```

For changes that don't start from an issue — refactors, hotfixes,
exploratory deltas — `mol-pr-blast-radius` is a standalone entry point
with the same analysis shape the planner runs inline.

### Self-review an outgoing PR

```sh
gc pr-pipeline pr review 1234 --rig api-server
```

Scorecard against 11 categories (behavioral correctness, contract
fidelity, blast radius, concurrency, error handling, security, resource
lifecycle, release safety, test evidence, architectural consistency,
debuggability). Pre-flags 7 recurring fixup themes. Verdict: `block`,
`request_changes`, or `approve`.

### Run the pre-push gate

```sh
gc pr-pipeline pr ship --rig api-server
```

Four-stage pipeline: simplify → iterate an adversarial multi-reviewer
panel (parallel reviewer subagents + adversarial synthesis) until clean →
mechanical gates (build/vet/test/docs) → readiness report. **STOPS at
the report.** Push and PR-open are explicit caller actions this formula
never performs.

### Override the worker agent

Default agent for all wrappers is `polecat`. Override with `--agent`:

```sh
gc pr-pipeline pr plan 1234 --rig api-server --agent claude
```

Or sling directly without the wrapper:

```sh
gc sling api-server/polecat mol-pr-start --formula --var issue=1234
```

## Pack contents

```
pr-pipeline/
├── pack.toml
├── formulas/
│   ├── mol-pr-start.formula.toml          6-step planner
│   ├── mol-pr-blast-radius.formula.toml   5-step impact mapper
│   ├── mol-pr-review.formula.toml         4-step outgoing-PR scorecard
│   └── mol-pr-ship.formula.toml           5-step pre-push gate
├── commands/
│   └── pr/
│       ├── plan/         (run.sh + help.md)
│       ├── blast-radius/
│       ├── review/
│       └── ship/
└── templates/
    └── adoption-review-comment.md         canonical reviewer-side
                                           comment template (Form 1: no
                                           maintainer changes; Form 2:
                                           maintainer fixups present)
```

### Shared templates

`templates/adoption-review-comment.md` is the canonical structure for the
synthesis comment a maintainer posts when adopting a contributor PR. Two
forms cover all four merge paths the `pr-review` pack's `mol-adopt-pr`
distinguishes (no maintainer changes vs. maintainer fixups present).

The template documents:

- The two literal comment shapes (Form 1 / Form 2)
- All inputs the renderer needs (PR metadata, synthesis + scorecard from
  the review run, maintainer-fixup log/diff, final tip SHA, model list,
  iteration count)
- Rendering rules per `{model-rendered}` field (the orchestration is
  mechanical; the prose is the model's job)
- Validation gates enforced before posting (verbatim opener, footer
  literal, section order, SHA prefix match, iteration-count match)
- A fail-stop fallback for malformed renders (write rejected text and
  STOP — never post a partial comment)
- Path-specific adjustments for the four merge paths (A / B / C / D)

The reviewer-side counterpart to this pack's `mol-pr-review`
author-side scorecard. Both produce structured findings against the same
11-category scorecard so contributors get consistent feedback shape
regardless of direction.

The full workflow for each formula lives in step descriptions. A coding
agent (polecat or equivalent) follows them in sequence; gates can
short-circuit with an early exit.

## Why formula-shaped, not agent-as-directory

This pack ships **formulas**, not standing agents. Each formula is a
bounded workflow ("plan one PR, exit" / "score one PR, exit") rather
than a long-lived role like mayor or polecat. The consumer city's
existing coding worker (whatever it's named) runs the formula — no
extra agent deployment required.

Standing roles (mayor, polecat, witness, refinery) belong in their own
packs as `agents/<name>/` directories. Bounded workflows belong as
`formulas/mol-<name>.formula.toml` with the workflow inlined in step
descriptions.
