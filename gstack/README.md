# gstack Gas City Pack

This pack adapts the [garrytan/gstack](https://github.com/garrytan/gstack)
methodology — a founder-style sprint that runs YC-office-hours intake,
multi-perspective plan review, staff code review, QA, security review, and
release readiness — into durable Gas City workflows. You get one full-lifecycle
formula, `gstack-build`, that keeps the recognizable garrytan/gstack sprint:

Think -> Plan -> Build -> Review -> Test -> Ship -> Reflect

Upstream gstack is a Claude Code skills pack whose roles (YC Office Hours,
CEO/founder review, engineering review, design review, staff review, QA, CSO
security, documentation, release engineering) hand work to each other through
subagents. In this pack those roles are providerless Gas City agents, and their
multi-agent handoffs are Gas City fanouts: persistent, observable, and
retryable through the workflow graph.

## When to choose gstack

- You want the strictest pre-ship gating of the methodology packs: gstack adds
  dedicated `qa` and `release-readiness` stages between code review and
  finalize, so nothing finalizes without browser-oriented QA evidence and a
  documentation/ship/deploy readiness pass.
- You want founder- and PM-flavored review perspectives. Plan review fans out
  CEO/founder scope, design, engineering, and developer-experience lanes;
  requirements come from an office-hours interrogation (demand, status quo,
  user specificity, narrow wedge) rather than a plain requirements template.
- You are comfortable answering questions during the run. Unlike `build-basic`
  and the other methodology packs, gstack defaults both `interaction_mode` and
  `review_mode` to `interactive`, because raw gstack is intentionally
  conversation-heavy. You can override both for automation.
- If you want a leaner run, pick `build-basic` (single-lane review, no extra
  gates) or another methodology pack (Compound Engineering, Superpowers, BMAD);
  they share the same `build-base` contract, so switching later is a one-line
  formula change.

## Quick start

These steps go from a fresh machine to a completed gstack sprint.

1. Install Gas City and create a city:

   ```sh
   brew install gascity
   gc init ~/my-city && cd ~/my-city && gc start
   ```

2. Add the repository you want to build in as a rig:

   ```sh
   mkdir proj && cd proj && git init && gc rig add .
   ```

3. Import this pack at city scope. From the city directory — this writes the
   import, fetches the latest release, and pins it in `packs.lock`, no clone
   needed:

   ```sh
   gc import add https://github.com/gastownhall/gascity-packs.git//gstack
   ```

   Then import the Gas City roles pack on the rig: the methodology pack
   supplies the formulas and `gstack.*` agents, and the rig-level
   `gascity/roles` import supplies the `gc.*` role agents (run operator,
   publisher, implementation workers) that the formulas route to. In your
   `city.toml`, then `gc import install`:

   ```toml
   [[rigs]]
   name = "proj"

   [rigs.imports.gc]
   source = "https://github.com/gastownhall/gascity-packs.git//gascity/roles"
   ```

   Contributors working on the packs themselves can clone
   `https://github.com/gastownhall/gascity-packs` and point either `source`
   at the local path (for example `../gascity-packs/gstack`) instead.

4. Create a bead for the goal and sling it onto `gstack-build`. The formula
   declares `target_required = true`, so it is launched against a bead (or
   convoy), not with `--formula`:

   ```sh
   gc bd create "Add CSV export to the reports page"
   gc sling gc.run-operator <bead-id> --on gstack-build \
     --var artifact_root=plans/csv-export/build \
     --var drain_policy=separate
   ```

5. The run walks the build-base stage sequence. With gstack's overrides and
   additions, that means: `prepare`, office-hours `requirements`, autoplan
   `plan`, the `plan-review` fanout (founder scope, design, engineering,
   developer experience), `decompose` into an implementation convoy,
   `implement` (a drain of `gstack-work` items), the `review` fanout (staff,
   QA evidence, CSO security, gap analysis), then the two pack-added gates —
   `qa` (browser QA plus regression-test evidence) and `release-readiness`
   (documentation, ship readiness, deployment readiness) — before `finalize`
   writes the sprint report and `publish` optionally pushes or opens a PR.
   In the default interactive modes, expect the office-hours and review lanes
   to ask you questions before proceeding.

6. Artifacts land under your `artifact_root` (here
   `plans/csv-export/build/` in the rig): requirements, plan, decomposition,
   implementation summary, review report, QA summary, release-readiness
   summary, and the final sprint report. Inspect the formula surface at any
   time with:

   ```sh
   gc formula catalog --json
   gc formula show gstack-build --json
   ```

## Stage map

`gstack-build` extends `build-base` and keeps the inherited anchor order
`prepare -> requirements -> plan -> plan-review -> decompose ->
implement/implement-same-session -> summarize-implementation -> review ->
finalize -> publish`. No base anchor is renamed, skipped, or reordered;
`prepare` stays inherited.

| Stage | gstack behavior | Route |
| --- | --- | --- |
| `requirements` | Office-hours intake: demand, status quo, user specificity, narrow wedge, observation, future fit | `gstack.office-hours` |
| `plan` | Autoplan draft | `gstack.founder-reviewer` |
| `plan-review` | `gstack-plan-review` fanout: founder scope, design, engineering, developer-experience lanes | `gstack.review-synthesizer` |
| `decompose` | Implementation convoy creation | `gstack.decomposer` |
| `implement` / `implement-same-session` | Drains `gstack-work` (separate) or `gstack-work-item` (same-session) | `{implementation_target}` |
| `summarize-implementation` | Verifies exact convoy closure and worktree-bound commit evidence, then writes the canonical implementation summary | `gc.run-operator` |
| `review` | `gstack-code-review` fanout: staff, QA-evidence, CSO-security, gap-analysis lanes | `gstack.review-synthesizer` |
| `qa` (pack-added) | `gstack-qa-review` fanout: browser QA and regression-test evidence | `gstack.qa-lead` |
| `release-readiness` (pack-added) | `gstack-release-readiness` fanout: documentation, ship readiness, deployment readiness | `gstack.release-engineer` |
| `finalize` | Sprint report under the artifact root | `gstack.release-engineer` |
| `publish` | Optional push / PR lane | `gc.publisher` |

`qa` and `release-readiness` are the only pack-added steps, anchored after
`review` and before `finalize`: `qa` needs `review`, `release-readiness` needs
`qa`, `finalize` is rewired to need `release-readiness`, and `publish` still
needs `finalize`. Each expands a check-gated loop
(`implementation-review-approved.sh`; QA allows 6 attempts, release-readiness
4). QA synthesis owns the semantic `approve|iterate` result, followed by one
mode-selected terminal: agent/interactive mode may apply fixes and owns
`done|iterate`, while report mode records findings without mutation and owns
`reported`. Release-readiness synthesis owns `done|iterate` in
agent/interactive mode and feeds a current-attempt `reported` terminal in
report mode. Their outputs are the QA summary recorded on the workflow root at
`gc.build.qa_summary_path` before release readiness begins and the readiness
summary at `gc.build.release_readiness_summary_path` before finalize begins.
Each summary preserves `approved`, `changes_required`, or `blocked`; the final
gate requires a blocked final report whenever report-mode findings remain.

The `review` anchor works the same way: `gstack-code-review` records the
review context, fans out the staff, QA-evidence, CSO-security, and
gap-analysis lanes, fans in at `synthesize-code-review`, and loops an
`apply-review-findings` lane (routed to the caller-selected implementation
target) through a bounded graph check until `code_review.verdict=done` lands
on the workflow root. In report mode a separate read-only terminal records
`reported`, and the loop check requires that terminal from the current attempt
instead of accepting a pre-existing root report path. `gstack-fix-loop`
carries the same review-fix contract for standalone adapter use.

The QA and release-readiness expansion finalizers run a second executable
binding check after they update root metadata. It requires each selected root
path to equal the one report terminal from the current loop epoch and rejects
missing, duplicate, stale, non-canonical, or outside-artifact-root evidence.

Supported modes and drain policies, as declared in
`[metadata.gc.methodology]` of `gstack-build`:

- `interaction_modes`: `interactive`, `autonomous`, `headless` (inherited
  `interaction_mode` var; the pack pins the default to `interactive` because
  raw gstack is conversation-heavy)
- `review_modes`: `report`, `agent`, `interactive` (inherited `review_mode`
  var; the pack pins the default to `interactive` to match the office-hours
  posture)
- `implementation_strategy`: `drain` with `allowed_drain_policies` of
  `separate` (drains `gstack-work` item formulas with exclusive member access)
  and `same-session` (drains `gstack-work-item` in one shared single-lane
  session with `on_item_failure = "skip_remaining"`; a machine-gated prepare
  step creates or reuses a deterministic sibling worktree and records it on
  every source member before implementation)

The native stage formulas extend the matching base methodology contracts:
`gstack-planning` (`planning-base`), `gstack-decomposition`
(`decomposition-base`), `gstack-implementation` (`implement`), `gstack-review`
(`code-review-base`), and `gstack-fix-loop` (`fix-loop-base`), plus the drain
formulas `gstack-work` (`do-work`) and `gstack-work-item` (`do-work-item`).

## Customization

Pass any of these as `--var k=v` on the launch command. The selector vars also
let shared Gas City adapters pick gstack stages without using `gstack-build`.

| Variable | Default | What it changes |
| --- | --- | --- |
| `interaction_mode` | `interactive` | Human participation in planning and gates. `interactive` preserves blocking questions and approval menus; `autonomous` records assumptions instead of asking; `headless` never blocks. Note: gstack defaults this to `interactive`, unlike the other methodology packs. |
| `review_mode` | `interactive` | Review authority. `report` writes findings only, without applying fixes or opening release paths; `agent` is a structured machine handoff whose fixes are applied by the loop; `interactive` preserves a raw top-level review that may apply safe fixes. Also defaulted to `interactive` here. |
| `drain_policy` | `separate` | `separate` runs each implementation bead in its own worktree lane in parallel by convoy dependencies; `same-session` runs all items in one shared single-lane session. |
| `implementation_target` | `gstack.implementer` | The role that implements drained work items and applies review/QA fix findings. |
| `artifact_root` | (required input) | Directory under the rig where all stage artifacts land. |
| `push` | `false` | Allow the publish stage to push after all checks pass. |
| `open_pr` | `false` | Allow the publish stage to open a PR after all checks pass. |
| `max_iterations` | `10` | Maximum implementation/review fix attempts. |
| `planning_formula` | `gstack-planning` | Selector: planning methodology formula. |
| `decomposition_formula` | `gstack-decomposition` | Selector: decomposition methodology formula. |
| `implementation_formula` | `gstack-implementation` | Selector: implementation entry formula. |
| `implementation_item_formula` | `gstack-work-item` | Selector: single-item implementation formula for shared drains. |
| `code_review_formula` | `gstack-review` | Selector: code-review methodology formula. |
| `review_fix_formula` | `gstack-fix-loop` | Selector: review-fix loop formula. |

Step prompt text is also customizable without touching the formula graph. Each
stage reads its body from `assets/workflows/gstack-build/<step-id>.md`, and a
file at the same relative path in a higher-priority city or local pack layer
shadows it. For example, to tighten the QA gate, create
`assets/workflows/gstack-build/qa.md` in your city assets:

```markdown
Run gstack QA against the staging deployment, not a local build.

- Exercise the changed user flow end to end in a real browser session.
- Attach the regression test command output for every changed package.
- Treat missing reproduction steps for any found defect as iterate, not done.
```

For the full customization contract (basic asset shadowing and advanced step
override rules), see "Stable Workflow Override Interface" in the
[gascity pack README](../gascity/README.md).

## Examples

Interactive sprint on a new feature (all defaults: interactive intake and
review, separate drain):

```sh
gc bd create "Add CSV export to the reports page"
gc sling gc.run-operator <bead-id> --on gstack-build \
  --var artifact_root=plans/csv-export/build \
  --var drain_policy=separate
```

Autonomous run that pushes and opens a PR — overrides both interactive
defaults so no lane blocks on a human, and enables the publish side effects:

```sh
gc bd create "Migrate the settings page to the v2 form components"
gc sling gc.run-operator <bead-id> --on gstack-build \
  --var artifact_root=plans/settings-v2/build \
  --var drain_policy=separate \
  --var interaction_mode=autonomous \
  --var review_mode=agent \
  --var push=true \
  --var open_pr=true
```

Same-session drain for a small change — keeps every implementation item in one
shared worktree and conversation instead of parallel lanes:

```sh
gc bd create "Fix the off-by-one in pagination page counts"
gc sling gc.run-operator <bead-id> --on gstack-build \
  --var artifact_root=plans/pagination-fix/build \
  --var drain_policy=same-session
```

## What's vendored

The vendored upstream files under `vendor/gstack` are reference material;
`vendor/gstack/upstream.toml` records the upstream source repository, the
pinned commit, and the MIT license. The installed files under `skills/`
(office-hours, autoplan, plan-eng-review, review, investigate,
document-release) expose the same vocabulary for agents. Runtime execution is
owned by formulas, beads, and Gas City graph lanes.

Raw-framework subagents become Gas City fanouts. Do not preserve upstream
subagent behavior as provider-native subagents; model that work as formulas or
expansion children. Every lane in this pack routes through `gc.run_target` to
a providerless `gstack.*` agent, a `gc.*` role, or the caller-selected
implementation target — no lane dispatches provider-native subagents.

## Compatibility ledger

The pack-local compatibility ledger lives at
[`gstack/REQUIREMENTS.md`](./REQUIREMENTS.md) and records the build-base
contract proofs — the inherited `gc` import, the preserved anchor order, the
qa/release-readiness insertion between review and finalize — together with the
evidence commands that reproduce each claim.
